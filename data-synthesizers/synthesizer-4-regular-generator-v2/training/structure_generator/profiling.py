"""固定候选、配对回放的分阶段性能测量；保留真实三轮验收与数据库保存。"""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import platform
import time

import mcscai_engine

from ..serialization import digest, write_json
from .repository import Repository
from .timing import Timings
from .worker import generate
from .runtime import engine_identity


def cases(count, large_count):
    result = []
    for depth in (2, 3, 4):
        for name in ('dense', 'large', 'extension'):
            options = dict(search=True, simulation_budget=128 if name == 'large' else 96,
                           min_extensions=1, extension_placement={2:'front', 3:'rear', 4:'any'}[depth],
                           min_saturated_extensions=int(name == 'extension'))
            targets, density = (10 if depth == 2 or name == 'extension' else 13), .4
            if name == 'extension':
                density = .35
            if name == 'large':
                targets, density = 20, .35 if depth == 4 else .25
                options.update(min_long_side=10, min_short_side=6)
            result.append(dict(name=f'{depth}-{name}', depth=depth, options=options,
                               targets=targets, density=density,
                               count=large_count if depth == 2 and name == 'large' else count))
    return result


def measured_job(payload):
    job, instrumented = payload
    timer = Timings()
    started, cpu = time.perf_counter(), time.process_time()
    if instrumented:
        with timer.installed(), timer.stage('其他筛选与打包'):
            result = generate(job)
    else:
        result = generate(job)
    elapsed, cpu = time.perf_counter()-started, time.process_time()-cpu
    return dict(result=result, seconds=elapsed, cpu_seconds=cpu,
                timing=timer.report() if instrumented else {})


def warm(_):
    time.sleep(.02)
    return os.getpid()


def stable(value):
    """只排除实际计时字段，其余结构、判定、机制与失败原因全部核对。"""
    if isinstance(value, dict):
        return {k:stable(v) for k,v in value.items() if k != 'seconds'}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def measure(pool, jobs, directory, instrumented):
    repo = Repository(directory, dict(measurement=True, instrumented=instrumented))
    quota = {(jobs[0][2], jobs[0][3]):len(jobs)}
    samples, save_seconds = [], 0.0
    started = time.perf_counter()
    try:
        futures = [pool.submit(measured_job, (job, instrumented)) for job in jobs]
        for future in as_completed(futures):
            sample = future.result()
            tick = time.perf_counter()
            repo.save(sample['result'], quota)
            save_seconds += time.perf_counter()-tick
            samples.append(sample)
        tick = time.perf_counter()
        saved = repo.report('性能测量完成', quota)
        export_seconds = time.perf_counter()-tick
    finally:
        repo.close()
    seconds = time.perf_counter()-started
    samples.sort(key=lambda v:v['result']['index'])
    totals, calls, traffic = defaultdict(Counter), Counter(), Counter()
    for sample in samples:
        for name, values in sample['timing'].get('stages', {}).items():
            totals[name].update(values)
        calls.update(sample['timing'].get('calls', {}))
        traffic.update(sample['timing'].get('traffic', {}))
    summary = dict(attempts=len(jobs), accepted=sum('row' in s['result'] for s in samples),
                   unique=saved['accepted'], wall_seconds=seconds,
                   unique_per_second=saved['accepted']/seconds,
                   worker_seconds=sum(s['seconds'] for s in samples),
                   worker_cpu_seconds=sum(s['cpu_seconds'] for s in samples),
                   save_seconds=save_seconds, export_seconds=export_seconds,
                   reasons=saved['reasons'], stages={k:dict(v) for k,v in totals.items()},
                   calls=dict(calls), traffic=dict(traffic))
    # 测量归档写盘放在计时之外，数据库与正式格式导出已计时。
    write_json(directory/'samples.json', samples)
    return summary, {s['result']['index']:digest(stable(s['result'])) for s in samples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=64, help='每个专项的固定候选数')
    parser.add_argument('--large-count', type=int, default=320, help='两格大尺寸的固定候选数')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--seed', type=int, default=2026092514)
    parser.add_argument('--cases', nargs='+', help='只测指定专项，如 2-large 4-dense')
    args = parser.parse_args()
    if min(args.count, args.large_count, args.workers) < 1:
        parser.error('候选数量与进程数量必须大于零')
    selected = cases(args.count, args.large_count)
    if args.cases:
        if set(args.cases)-{c['name'] for c in selected}:
            parser.error('未知专项')
        selected = [c for c in selected if c['name'] in args.cases]
    args.output.mkdir(parents=True, exist_ok=False)
    sources = {str(p):p.read_text() for p in Path('training').rglob('*.py')}
    write_json(args.output/'source.json', sources)
    report = dict(source_digest=digest(sources), seed=args.seed, workers=args.workers,
                  python=platform.python_version(), engine=mcscai_engine.__version__,engine_build=engine_identity(),
                  cpu_count=os.cpu_count(), cases=[], complete=False,
                  notes=['固定候选预算，不使用预览配额收尾；专项依次执行。',
                         '阶段占比为工作进程累计用时，不与四进程墙钟时间相加。',
                         'Rust接口含命令解析、模拟、快照构造和JSON编码，未细分内部耗时。',
                         '两格密集按编号交替请求入口延伸，其余专项每条要求入口延伸。',
                         '不含展示裁减、回拉对照和服务器发布。'])
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        report['warm_worker_pids'] = sorted(set(pool.map(warm, range(args.workers*4))))
        report['pool_startup_seconds'] = time.perf_counter()-started
        for case_index, case in enumerate(selected):
            jobs = []
            for index in range(case['count']):
                options = dict(case['options'])
                if case['name'] == '2-dense':
                    options.update(min_extensions=index % 2, extension_placement='any')
                jobs.append((index,args.seed,'推拉结合多时序',case['depth'],True,
                             case['targets'],case['density'],options))
            write_json(args.output/case['name']/'jobs.json', jobs)
            cell = dict(conditions=case)
            signatures = {}
            # 交替次序，避免把首次执行或机器温度差异全部归给计时钩子。
            modes = ('baseline','instrumented') if case_index % 2 == 0 else ('instrumented','baseline')
            for mode in modes:
                print(json.dumps(dict(case=case['name'],mode=mode,status='开始'),ensure_ascii=False),flush=True)
                cell[mode], signatures[mode] = measure(pool,jobs,args.output/case['name']/mode,
                                                      mode == 'instrumented')
                print(json.dumps(dict(case=case['name'],mode=mode,
                    seconds=round(cell[mode]['wall_seconds'],3),unique=cell[mode]['unique']),ensure_ascii=False),flush=True)
            cell['identical_results'] = signatures['baseline'] == signatures['instrumented']
            cell['worker_cpu_overhead_ratio'] = (cell['instrumented']['worker_cpu_seconds'] /
                                                 cell['baseline']['worker_cpu_seconds']-1)
            report['cases'].append(cell)
            write_json(args.output/'report.json',report)
            if not cell['identical_results']:
                raise RuntimeError('计时前后候选结果不一致，不能用于性能结论')
    report['complete'] = True
    write_json(args.output/'report.json',report)


if __name__ == '__main__':
    main()

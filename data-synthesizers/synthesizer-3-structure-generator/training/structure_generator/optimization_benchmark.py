"""回放冻结候选，核对优化前后结构、判定、覆盖与真实耗时。"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import time

from ..serialization import digest, write_json
from .profiling import stable, warm, measured_job
from .repository import Repository
from .runtime import engine_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--allow-pruned-failures', action='store_true')
    parser.add_argument('--options', type=json.loads, default={})
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    old = json.loads((args.source/'report.json').read_text())
    report = dict(cases=[], complete=False, source=str(args.source), workers=args.workers,engine=engine_identity(),
                  options=args.options)
    write_json(args.output/'source.json', {str(p):p.read_text() for p in Path('training').rglob('*.py')})
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(warm,range(args.workers*4)))
        for cell in old['cases']:
            name = cell['conditions']['name']
            jobs = json.loads((args.source/name/'jobs.json').read_text())
            for job in jobs:
                job[-1].update(args.options)
            reference = {s['result']['index']:s['result'] for s in json.loads(
                (args.source/name/'baseline/samples.json').read_text())}
            repo = Repository(args.output/name, dict(benchmark=True))
            quota = {(jobs[0][2],jobs[0][3]):len(jobs)}
            started = time.perf_counter()
            results, differences, lost, samples, changed_valid = [], [], [], [], []
            for f in as_completed([pool.submit(measured_job,(j,False)) for j in jobs]):
                sample = f.result()
                samples.append(sample)
                result = sample['result']
                repo.save(result,quota)
                before = reference[result['index']]
                # 新增执行选项不属于结构或模拟结果差异。
                def comparable(v):
                    v = stable(v)
                    v.pop('requested',None)
                    if 'row' in v:
                        v['row'].pop('requested_sampling',None)
                    return v
                if digest(comparable(result)) != digest(comparable(before)):
                    differences.append(result['index'])
                    if 'row' in result or 'row' in before:
                        changed_valid.append(result['index'])
                if 'row' in before and ('row' not in result or result['row']['id'] != before['row']['id']):
                    lost.append(result['index'])
                results.append(result)
            saved = repo.report('优化对照完成',quota)
            repo.close()
            seconds = time.perf_counter()-started
            accepted = [r['row'] for r in results if 'row' in r]
            summary = dict(name=name,attempts=len(jobs),seconds=seconds,
                           worker_cpu_seconds=sum(s['cpu_seconds'] for s in samples),
                           baseline_seconds=cell['baseline']['wall_seconds'],unique=saved['accepted'],
                           accepted=len(accepted),differences=differences,lost=lost,
                           changed_valid=changed_valid,
                           speedup=cell['baseline']['wall_seconds']/seconds,
                           reasons=saved['reasons'])
            write_json(args.output/name/'results.json',results)
            report['cases'].append(summary)
            write_json(args.output/'report.json',report)
            print(json.dumps(summary,ensure_ascii=False),flush=True)
            if lost or changed_valid or (differences and not args.allow_pruned_failures):
                raise RuntimeError('优化结果未通过冻结候选一致性核对')
    report['complete'] = True
    write_json(args.output/'report.json',report)


if __name__ == '__main__':
    main()

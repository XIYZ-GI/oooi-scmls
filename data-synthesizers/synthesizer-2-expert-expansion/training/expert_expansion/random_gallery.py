"""随机延伸和终止单元连接，运行后读出目标时序，保存完整尝试记录和网页展示。"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import random
import time

import mcscai_engine

from ..serialization import digest, write_json
from .admission import admit
from .composition import compose
from .config import ROOT
from .gallery_publish import describe, publish, select

_library = None


def initialize(library):
    global _library
    _library = library


def attempt(index, seed, limits, max_nodes):
    rng = random.Random(f'{seed}:{index}')
    diagnostics = {}
    stop = rng.uniform(.03, .65)
    row = compose(_library, rng, max_nodes=max_nodes, limits=limits,
                  stop_probability=stop, diagnostics=diagnostics)
    record = dict(attempt=index, seed=seed, stop_probability=stop, diagnostics=diagnostics)
    if row is None:
        return dict(**record, accepted=False, reason=diagnostics.get('reason', '组合未完成'))
    # 周期随实际连接数量留出运行时间，时序仍由模拟器读取。
    row['task']['max_ticks'] = max(64, 8*len(row['topology'])+24)
    row = admit(row)
    row['sampling'] = record
    return dict(**record, accepted=row['evaluation']['accepted'],
                reason=row['evaluation']['reason'], row=row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempts', type=int, default=2048)
    parser.add_argument('--seed', type=int, default=2026092209)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--max-nodes', type=int, default=48)
    parser.add_argument('--max-width', type=int, default=64)
    parser.add_argument('--max-height', type=int, default=64)
    parser.add_argument('--max-depth', type=int, default=32)
    parser.add_argument('--max-volume', type=int, default=32768)
    parser.add_argument('--max-targets', type=int, default=192)
    parser.add_argument('--show', type=int, default=12)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--api', default='http://127.0.0.1:8010/api/datasets')
    args = parser.parse_args()
    if any(getattr(args, k) < 1 for k in ('attempts', 'workers', 'max_nodes', 'max_width',
                                        'max_height', 'max_depth', 'max_volume', 'max_targets', 'show')):
        parser.error('数量和资源上限必须为正整数')
    output = args.output or ROOT/f'random-gallery-{args.seed}'
    output.mkdir(parents=True, exist_ok=True)
    limits = {k: getattr(args, 'max_'+k) for k in ('width', 'height', 'depth', 'volume', 'targets')}
    library = json.loads((ROOT/'module-library.json').read_text())
    config = dict(seed=args.seed, limits=limits, max_nodes=args.max_nodes,
                  library_sha256=digest(library['modules']), engine_version=mcscai_engine.__version__,
                  protocol='random_composition_activation_diagnostic_v1')
    config_path = output/'config.json'
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError('此目录保存了不同配置的随机探索，请指定新的输出目录')
    write_json(config_path, config)
    records_path = output/'attempts.jsonl'
    records = {}
    if records_path.exists():
        for line in records_path.read_text().splitlines():
            r = json.loads(line)
            records[r['attempt']] = r
    started = time.monotonic()
    reasons = Counter(r['reason'] or '完整通过' for r in records.values())
    accepted = sum(r['accepted'] for r in records.values())
    with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize, initargs=(library,)) as pool:
        pending = [pool.submit(attempt, i, args.seed, limits, args.max_nodes)
                   for i in range(args.attempts) if i not in records]
        with records_path.open('a') as stream:
            for future in as_completed(pending):
                r = future.result()
                records[r['attempt']] = r
                stream.write(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n')
                stream.flush()
                reasons[r['reason'] or '完整通过'] += 1
                accepted += r['accepted']
                if len(records) % 32 == 0:
                    progress = dict(completed=len(records), accepted=accepted,
                                    reasons=dict(reasons), seconds=time.monotonic()-started)
                    write_json(output/'progress.json', progress)
                    print(json.dumps(progress, ensure_ascii=False), flush=True)
    rows = [r['row'] for _, r in sorted(records.items()) if r['accepted']]
    unique = {r['id']: r for r in rows}
    stats = [describe(r) for r in unique.values()]
    metrics = ('width', 'height', 'depth', 'targets', 'groups', 'nodes', 'branches', 'blocks')
    report = dict(**config, attempts=len(records), assembled=sum('row' in r for r in records.values()),
                  accepted=accepted, unique_structures=len(unique),
                  connection_groups=len({s['group'] for s in stats}),
                  target_geometries=len({s['geometry'] for s in stats}),
                  modules_used=len({n['module'] for r in unique.values() for n in r['topology']}),
                  reasons=dict(reasons),
                  observed_ranges={k: [min(s[k] for s in stats), max(s[k] for s in stats)]
                                   for k in metrics} if stats else {},
                  distributions={k: dict(Counter(s[k] for s in stats)) for k in metrics},
                  seconds=time.monotonic()-started,
                  scope='现有单元库的随机连接构造；先造结构、再观测时序。有限采样范围不是理论上限，也不是神经网络成绩。')
    selected = select(list(unique.values()), args.show)
    write_json(output/'report.json', report)
    write_json(output/'selected.json', [describe(r) for r in selected])
    if args.publish:
        publish(selected, output, args.seed, args.api)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

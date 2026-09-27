"""复用性能测量结果，单独测量任务派发和完整结果回传的通信成本。"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time

from ..serialization import digest, write_json
from .profiling import warm


_RESULTS = []


def initialize(results):
    global _RESULTS
    _RESULTS = results


def replay(index):
    return _RESULTS[index]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if min(args.workers, args.repeats) < 1:
        parser.error('进程数与重复次数必须为正')
    report = json.loads((args.source/'report.json').read_text())
    if not report['complete']:
        parser.error('分阶段测量尚未完成')
    results = []
    for case in report['cases']:
        samples = json.loads((args.source/case['conditions']['name']/'baseline/samples.json').read_text())
        results.extend(s['result'] for s in samples)
    reference = digest(results)
    measured = dict(count=len(results), workers=args.workers, rounds=[],
                    notes=['工作进程预先加载同批完整结果，只派发编号并回传原结果。',
                           '包含任务调度、进程间序列化与接收，不含构造、验收、保存。',
                           '属于独立通信校准，不能直接从正常生成墙钟时间中扣除。'])
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize, initargs=(results,)) as pool:
        measured['warm_worker_pids'] = sorted(set(pool.map(warm, range(args.workers*4))))
        measured['startup_seconds'] = time.perf_counter()-started
        for _ in range(args.repeats):
            started = time.perf_counter()
            returned = list(pool.map(replay, range(len(results)), chunksize=1))
            seconds = time.perf_counter()-started
            if digest(returned) != reference:
                raise RuntimeError('进程回传内容与源结果不一致')
            measured['rounds'].append(dict(seconds=seconds, per_candidate_ms=seconds/len(results)*1000))
    measured['source_digest'] = digest(Path(__file__).read_text())
    write_json(args.source/'transfer.json', measured)
    print(json.dumps(measured, ensure_ascii=False))


if __name__ == '__main__':
    main()

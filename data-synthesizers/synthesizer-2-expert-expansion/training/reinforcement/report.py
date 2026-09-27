"""汇总已保存的正式训练产物，不再生成结构或执行模拟。"""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

from ..serialization import digest, write_json
from .demands import geometry


def main():
    parser = argparse.ArgumentParser(description='汇总第五阶段实际训练和验收记录')
    parser.add_argument('--runs', required=True)
    parser.add_argument('--data', default='data/generation/stage5')
    args = parser.parse_args()
    root, data = Path(args.runs), Path(args.data)
    totals, failure, dimensions = Counter(), Counter(), Counter()
    sources = defaultdict(Counter)
    successful_tasks, successful_structures, geometries = set(), set(), set()
    initial_experts = {geometry(json.loads(line)['task']) for line in (data/'experts.jsonl').read_text().splitlines()}
    for path in sorted((root/'rollouts').glob('*.jsonl.gz')):
        with gzip.open(path, 'rt') as handle:
            for line in handle:
                row = json.loads(line)
                task, evaluation, source = row['task'], row['evaluation'], row['source']
                accepted = evaluation['accepted']
                totals['candidates'] += 1
                totals['accepted'] += accepted
                totals['simulator_runs'] += evaluation['simulator_started']
                totals['simulated_ticks'] += evaluation['simulated_ticks']
                sources[source]['candidates'] += 1
                sources[source]['accepted'] += accepted
                count, groups = len(task['targets']), max(t['order'] for t in task['targets'])
                dimensions[f'{task["width"]}x{task["height"]}x{task["depth"]}/{count}目标/{groups}组'] += 1
                if not accepted:
                    failure[evaluation['reason']] += 1
                else:
                    successful_tasks.add(digest(task))
                    successful_structures.add(digest([task, row['proposal']]))
                    geometries.add(geometry(task))
    metrics = [json.loads(line) for line in (root/'metrics.jsonl').read_text().splitlines()]
    report = {**dict(totals), 'sources': {k: dict(v) for k, v in sources.items()},
              'unique_successful_demands': len(successful_tasks),
              'unique_successful_task_structures': len(successful_structures),
              'unique_successful_geometries': len(geometries),
              'successful_geometries_outside_expert_demands': len(geometries-initial_experts),
              'failure_reasons': dict(failure), 'demand_dimensions': dict(dimensions),
              'optimizer_updates': sum(r['updates'] for r in metrics),
              'rollout_seconds': sum(r['rollout_seconds'] for r in metrics),
              'optimization_and_storage_seconds': sum(r['seconds']-r['rollout_seconds'] for r in metrics),
              'note': '成功结构是训练采样实际通过，不等同于保留需求泛化。专家外几何仍可能与历史课程有关。'}
    write_json(root/'rollout-summary.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'demand_dimensions'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

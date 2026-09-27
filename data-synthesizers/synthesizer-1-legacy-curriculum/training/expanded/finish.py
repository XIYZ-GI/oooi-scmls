"""按训练前冻结的目标汇总第四阶段结果，不以成功示例代替整体验收。"""

import argparse
from collections import Counter
import json
from pathlib import Path

from ..data import read_examples
from ..serialization import write_json


def main():
    parser = argparse.ArgumentParser(description='第四阶段完整分项验收')
    parser.add_argument('--runs', required=True)
    parser.add_argument('--data', default='data/generation/stage4')
    args = parser.parse_args()
    runs, data = Path(args.runs), Path(args.data)
    goals = json.loads((data/'stage-goals.json').read_text())
    reports, rows = {}, {}
    datasets = ['heldout', 'retention', 'thickness']
    if (data/'fresh.jsonl').exists():
        datasets.append('fresh')
    for name in datasets:
        reports[name] = json.loads((runs/('current-'+name)/'report.json').read_text())
        rows[name] = read_examples(runs/('current-'+name)/'results.jsonl')
    checkpoints = {r['checkpoint_sha256'] for r in reports.values()}
    if len(checkpoints) != 1:
        raise ValueError('全部集合必须由同一检查点生成')
    protocols = {r.get('sampling_protocol', 'legacy') for r in reports.values()}
    budgets = {r['candidate_budget'] for r in reports.values()}
    if len(protocols) != 1 or budgets != {8}:
        raise ValueError('全部集合必须采用同一生成协议和固定八候选预算')
    checks = {}
    for family in ('path_varied', 'path_four', 'dense'):
        group = reports['heldout']['families'].get(family, {'tasks': 0, 'successes': 0})
        checks[family] = (group['tasks'] >= goals['minimum_heldout_tasks_per_family'] and
                          group['successes']/max(group['tasks'], 1) >= goals['new_family_minimum_rate'])
    checks['four_timing_compact'] = any(r['accepted'] and max(t['order'] for t in r['task']['targets']) >= 4
                                      and r['actual_depth'] <= 3 for r in rows['heldout'])
    checks['frame7x5_15target_depth4'] = any(r['accepted'] and r['task']['width'] == 7 and r['task']['height'] == 5
        and len(r['task']['targets']) == 15 and r['actual_depth'] <= goals['dense_maximum_depth'] for r in rows['heldout'])
    checks['retention_total'] = reports['retention']['successes'] >= goals['retention_minimum_successes']
    checks['thickness'] = reports['thickness']['successes'] >= goals['thickness_minimum_successes']
    if 'fresh' in reports:
        for family in ('path_varied', 'path_four', 'dense'):
            group = reports['fresh']['families'].get(family, {'tasks': 0, 'successes': 0})
            checks['fresh_'+family] = group['tasks'] >= 8 and group['successes']/max(group['tasks'], 1) >= .75
    # 旧能力的各族最低保持量以阶段三已报告结果固定，不允许新课程掩盖退化。
    floors = {'legacy_parallel': 13, 'legacy_relay': 2, 'expert_compact': 3, 'strong_compact': 18,
              'mixed_two': 15, 'mixed_three': 37, 'strong_wide': 38, 'strong_staggered': 3}
    for family, minimum in floors.items():
        checks['retention_'+family] = reports['retention']['families'].get(family, {}).get('successes', 0) >= minimum
    result = {'stage4_complete': all(checks.values()), 'checks': checks, 'goals': goals,
              'checkpoint_sha256': next(iter(checkpoints)), 'reports': reports,
              'sampling_protocol': next(iter(protocols)), 'candidate_budget': 8,
              'scope': '新增路径骨架与四格密集输出组合的有限课程。独立人工来源继续单列，不代表任意布局时序。',
              'failed_tasks': {name: [{'task_id': r['task_id'], 'family': r['family'], 'task': r['task']} for r in values if not r['accepted']]
                               for name, values in rows.items()}}
    write_json(runs/'result.json', result)
    print(json.dumps({'阶段完成': result['stage4_complete'], '分项': checks}, ensure_ascii=False))


if __name__ == '__main__':
    main()

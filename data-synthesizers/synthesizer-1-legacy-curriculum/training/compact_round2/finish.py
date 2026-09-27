"""阶段验收：单一检查点、新组合、历史回归和同需求厚度对照。"""

from collections import Counter, defaultdict
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ..compact.mechanisms import analyze
from ..data import read_examples
from ..evaluator import evaluate
from ..serialization import digest, write_json
from .prepare import write_rows


DATA = Path('data/generation/stage3-coverage')
RUNS = Path('runs/stage3-coverage')


def benchmark(arm, checkpoint, subset):
    output = RUNS/(arm+'-'+subset)
    sha = hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
    if not (output/'report.json').exists():
        with (RUNS/(arm+'-'+subset+'.log')).open('w') as log:
            subprocess.run([sys.executable, '-m', 'training.benchmark', '--data', str(DATA/(subset+'.jsonl')),
                            '--checkpoint', checkpoint, '--output', str(output), '--split', 'test', '--limit', '1000',
                            '--candidates', '8', '--seed', '20260927'], stdout=log, stderr=subprocess.STDOUT, check=True)
    report = json.loads((output/'report.json').read_text())
    if report['checkpoint_sha256'] != sha:
        raise ValueError('已有评估与检查点摘要不一致')
    report['scope'] = ('新目标几何组合，混材共享训练来源机械骨架；不是跨原理泛化' if subset == 'heldout'
                       else '历史需求回归' if subset == 'regression' else '固定需求、改变允许厚度；没有找到不代表无解')
    write_json(output/'report.json', report)
    print(json.dumps({'arm': arm, 'subset': subset, 'families': report['families']}, ensure_ascii=False), flush=True)
    return report


def evidence(directory):
    groups = defaultdict(lambda: {'tasks': 0, 'successes': 0, 'mechanism_successes': 0})
    successful = []
    for row in read_examples(directory/'results.jsonl'):
        group = groups[row['family']]
        group['tasks'] += 1
        if not row['accepted']:
            continue
        group['successes'] += 1
        with gzip.open(directory/(row['task_id']+'.trace.json.gz'), 'rt') as f:
            proof = json.load(f)
        mechanisms = analyze(proof['trace'])
        valid = (bool(mechanisms['nonempty_pull_operations'] and mechanisms['mixed_boundaries_separated_in_motion'])
                 if row['family'].startswith('mixed_') else bool(mechanisms['strong_power_only_pairs']))
        group['mechanism_successes'] += valid
        proposal = row['proposals'][row['first_success_candidate']-1]
        zs = [b['position']['z'] for b in proposal['blocks']]
        successful.append({'task_id': row['task_id'], 'task': row['task'], 'family': row['family'],
                           'proposal': proposal, 'actual_depth': max(zs)-min(zs)+1,
                           'mechanisms': mechanisms, 'mechanism_valid': valid, 'ticks': proof['rounds'][0]['ticks']})
    return dict(groups), successful


def main():
    global DATA, RUNS
    parser = argparse.ArgumentParser(description='阶段冻结验收与完整运行证据')
    parser.add_argument('--data', default=str(DATA))
    parser.add_argument('--output', default=str(RUNS))
    parser.add_argument('--previous', default='runs/stage3-round2/best.pt')
    args = parser.parse_args()
    DATA, RUNS = Path(args.data), Path(args.output)
    summary = json.loads((RUNS/'training-summary.json').read_text())
    for field, filename in (('data_digest', 'examples.jsonl'), ('heldout_digest', 'heldout.jsonl')):
        if summary[field] != digest((DATA/filename).read_text()):
            raise ValueError('训练后数据或保留需求发生变化')
    regression = read_examples('data/generation/stage3/heldout.jsonl')+read_examples('data/generation/stage3/five-target-heldout.jsonl')
    if (DATA/'additional-regression.jsonl').exists():
        regression += read_examples(DATA/'additional-regression.jsonl')
    write_rows(DATA/'regression.jsonl', regression)
    tasks = read_examples(DATA/'heldout.jsonl')
    sweep = []
    for family, count, pool in [('mixed_two', 6, tasks+regression), ('mixed_three', 8, tasks+regression),
                               ('strong_wide', 10, tasks+regression), ('strong_compact', 5, regression)]:
        options = [r for r in pool if r['family'] == family and len(r['task']['targets']) == count]
        if not options:
            continue
        source = min(options, key=lambda r: digest(['thickness_fixed', r['task_id']]))
        for depth in (2, 3, 4):
            row = deepcopy(source)
            row['task']['depth'] = depth
            row['task_id'] = digest(row['task'])[:24]
            row['family'] = family+'_depth'+str(depth)
            sweep.append(row)
    sweep_path = DATA/'thickness.jsonl'
    content = ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in sweep)
    if sweep_path.exists() and sweep_path.read_text() != content:
        raise ValueError('厚度对照需求发生变化')
    sweep_path.write_text(content)
    checkpoints = {'previous': args.previous, 'current': str(RUNS/'best.pt')}
    frozen = {arm: hashlib.sha256(Path(path).read_bytes()).hexdigest() for arm, path in checkpoints.items()}
    freeze = RUNS/'frozen-checkpoints.json'
    if freeze.exists() and json.loads(freeze.read_text()) != frozen:
        raise ValueError('冻结模型发生变化')
    write_json(freeze, frozen)
    reports = {}
    for arm, path in checkpoints.items():
        for subset in ('heldout', 'regression', 'thickness'):
            reports[arm+'-'+subset] = benchmark(arm, path, subset)
    groups, successful = evidence(RUNS/'current-heldout')
    regression_groups, regression_successful = evidence(RUNS/'current-regression')
    goal = json.loads((DATA/'stage-goals.json').read_text())
    conditions = {}
    for family in goal['required_unseen_families']:
        r = groups.get(family, {})
        conditions[family] = r.get('mechanism_successes', 0)/max(1, r.get('tasks', 0)) >= goal['unseen_combination_minimum_rate']
    coverage = successful+regression_successful
    conditions['wide_counts'] = set(goal['required_wide_target_counts']) <= {
        len(r['task']['targets']) for r in coverage if r['family'] == 'strong_wide' and r['mechanism_valid'] and r['actual_depth'] <= 4}
    conditions['mixed_high_counts'] = set(goal['required_mixed_high_target_counts']) <= {
        len(r['task']['targets']) for r in coverage if r['family'].startswith('mixed_') and r['mechanism_valid'] and r['actual_depth'] <= 3}
    strong = regression_groups.get('strong_compact', {})
    conditions['compact_strong_rate'] = strong.get('mechanism_successes', 0)/max(1, strong.get('tasks', 0)) >= goal['compact_strong_regression_minimum_rate']
    conditions['compact_strong_counts'] = set(goal['required_compact_simultaneous_targets']) <= {
        len(r['task']['targets']) for r in regression_successful if r['family'] == 'strong_compact' and r['actual_depth'] == 2 and r['mechanism_valid']}
    legacy = [r for f, r in regression_groups.items() if f.startswith('legacy_')]
    conditions['legacy'] = sum(r['successes'] for r in legacy)/max(1, sum(r['tasks'] for r in legacy)) >= goal['legacy_regression_minimum_rate']
    conditions['expert_regression'] = regression_groups.get('expert_compact', {}).get('successes', 0) >= goal['expert_regression_minimum_successes']
    for family in goal['required_unseen_families']:
        if family in regression_groups:
            row = regression_groups[family]
            conditions[family+'_retention'] = row['mechanism_successes']/row['tasks'] >= 0.90
    # 并排厚度结果必须齐全；完整通过才作为实际占用厚度证据。
    conditions['thickness_coverage'] = len(sweep) == 12
    controls = []
    for family in ('mixed_two', 'mixed_three'):
        options = [r for r in successful if r['family'] == family and r['mechanism_valid']]
        if options:
            chosen = max(options, key=lambda r: len(r['task']['targets']))
            modified = deepcopy(chosen['proposal'])
            for b in modified['blocks']:
                if b['block']['kind'] == 'honey_block':
                    b['block']['kind'] = 'slime_block'
            control = evaluate(chosen['task'], modified)
            controls.append({'task_id': chosen['task_id'], 'family': family,
                             'change': '只将蜂蜜全部换为粘液，其他条件固定', 'evaluation': control})
    conditions['material_control'] = len(controls) == 2 and all(not c['evaluation']['accepted'] for c in controls)
    result = {'reports': reports, 'mechanism_groups': groups, 'regression_groups': regression_groups,
              'conditions': conditions, 'stage3_complete': all(conditions.values()),
              'successful': successful, 'regression_successful': regression_successful,
              'material_controls': controls, 'scope': goal['scope']}
    write_json(RUNS/'result.json', result)
    print(json.dumps({'阶段条件': conditions, '阶段完成': result['stage3_complete']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

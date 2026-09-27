"""补齐多目标分档、斜向供电和七至八目标多时序课程。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import time

from ..compact.curriculum import strong_rules
from ..compact.transforms import transform
from ..data import read_examples
from ..serialization import digest, write_json
from ..templates import block
from .config import PLAN
from .prepare import verify, write_rows
from .rules import diagonal_strong, geometry, mixed_rules
from .wide import wide_rules
from .staggered import staggered_rules


ROOT = Path('data/generation/stage3-coverage')


def select_strata(rows, per_count):
    result = []
    for family in sorted({r['family'] for r in rows}):
        for count in sorted({len(r['task']['targets']) for r in rows if r['family'] == family}):
            eligible = {r['task_id']: r for r in rows if r['family'] == family and len(r['task']['targets']) == count}
            ordered = sorted(eligible.values(), key=lambda r: digest(['coverage_selection', r['task_id']]))
            distinct, chosen = set(), []
            for r in ordered:
                if r['geometry'] not in distinct:
                    chosen.append(r); distinct.add(r['geometry'])
                if len(chosen) >= per_count:
                    break
            result += chosen
    return result


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    if (ROOT/'manifest.json').exists():
        raise ValueError('已有覆盖课程产物，禁止覆盖')
    started = time.monotonic()
    old = read_examples('data/generation/stage3/examples.jsonl')
    current = read_examples('data/generation/stage3-round2/examples.jsonl')
    fixed = {geometry(r['task']): ('fit' if r['split'] == 'train' else 'reserved') for r in old}
    fixed.update({r['geometry']: r['usage'] for r in current})
    for r in read_examples('data/generation/stage3/five-target-heldout.jsonl'):
        fixed[geometry(r['task'])] = 'reserved'
    experts = json.loads(Path('data/generation/stage1/expert-snapshot.json').read_text())
    enlarged = deepcopy(next(r for r in experts if r['name'] == '移动线15'))
    enlarged['height'] = 5
    enlarged['request']['blocks'] += [block(0, 4, -2, 'piston')]
    enlarged['reference']['targets'] += [dict(x=0, y=4, z=0, order=3)]
    prototypes = [*wide_rules(), *diagonal_strong(), *strong_rules(), *mixed_rules([enlarged]), *staggered_rules()]
    fresh = {}
    for r in prototypes:
        key = geometry(r['task'])
        if key not in fixed:
            fresh.setdefault((r['family'], len(r['task']['targets'])), set()).add(key)
    assignment = dict(fixed)
    for stratum, groups in fresh.items():
        ordered = sorted(groups, key=lambda g: digest(['coverage_split', g]))
        n = max(1, len(ordered)//6)
        for i, g in enumerate(ordered):
            assignment[g] = 'development' if i < n else 'new_combination' if i < 2*n else 'fit'
    candidates = []
    for row in prototypes:
        key = geometry(row['task'])
        use = assignment[key]
        # 旧保留集合仅继续作为历史回归；开发与保留的新答案不进入拟合。
        if use == 'reserved':
            continue
        row.update(geometry=key, usage=use)
        for swap, sx, sy, material in ((False, 1, 1, False), (True, 1, 1, False),
                                        (False, -1, 1, True), (True, -1, -1, True)):
            candidates.append(transform(row, swap, sx, sy, material))
    known_ids = {r['id'] for r in current}
    candidates = list({r['id']: r for r in candidates if r['id'] not in known_ids}.values())
    write_json(ROOT/'allocation.json', {'assignments': assignment, 'candidates': len(candidates)})
    accepted, rejected = [], []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for i, r in enumerate(pool.map(verify, candidates, chunksize=4)):
            (accepted if r['evaluation']['accepted'] else rejected).append(r)
            if (i+1) % 250 == 0:
                print(json.dumps({'制作': i+1, '有效': len(accepted), '总数': len(candidates)}, ensure_ascii=False), flush=True)
    records = [*current, *accepted]
    for usage in ('development', 'new_combination'):
        if {r['geometry'] for r in records if r['usage'] == usage} & {r['geometry'] for r in records if r['usage'] == 'fit'}:
            raise ValueError('新几何与拟合集合交叉')
    development = select_strata([r for r in records if r['usage'] == 'development'], 2)
    used_held = {geometry(r['task']) for r in read_examples('data/generation/stage3-round2/heldout.jsonl')}
    heldout = select_strata([r for r in records if r['usage'] == 'new_combination'
                            and r['geometry'] not in used_held], 4)
    # 旧开发拉驱诊断维持独立标签，最终报告不把它视为泛化。
    development += [r for r in read_examples('data/generation/stage3-round2/development.jsonl') if r['family'] == 'pull_compact'][:4]
    development = [{**r, 'source_group': r['group'], 'group': r['geometry'], 'split': 'validation'} for r in development]
    heldout = [{**r, 'source_group': r['group'], 'group': r['geometry'], 'split': 'test'} for r in heldout]
    write_rows(ROOT/'examples.jsonl', records)
    write_rows(ROOT/'development.jsonl', development)
    write_rows(ROOT/'heldout.jsonl', heldout)
    plan = {**PLAN, 'seed': 20260927, 'steps': 12000, 'initial_checkpoint': 'runs/stage3-round2/best.pt',
            'validation_interval': 2000, 'learning_rate': 0.00012, 'depth_slack_max': 2,
            'family_sampling': {'mixed_three': 0.22, 'mixed_two': 0.13, 'strong_compact': 0.20,
                                'strong_wide': 0.25, 'strong_staggered': 0.10, 'pull_compact': 0.04,
                                'expert_compact': 0.03, 'legacy': 0.03}}
    write_json(ROOT/'experiment-plan.json', plan)
    write_json(ROOT/'stage-goals.json', {
        'single_checkpoint': True, 'candidate_budget': 8, 'rounds': 3, 'load_blocks': 10,
        'unseen_combination_minimum_rate': 0.75,
        'required_unseen_families': ['mixed_two', 'mixed_three', 'strong_wide'],
        'required_wide_target_counts': [6, 7, 8, 9, 10, 11],
        'required_mixed_high_target_counts': [7, 8],
        'compact_strong_regression_minimum_rate': 0.75,
        'required_compact_simultaneous_targets': [4, 5],
        'legacy_regression_minimum_rate': 0.90,
        'expert_regression_minimum_successes': 1,
        'mechanisms': ['strong_power_only_pairs', 'nonempty_pull_operations', 'mixed_boundaries_separated_in_motion'],
        'thickness_comparison': '固定相同目标坐标、截面、时序、负载与周期，比较不同允许厚度下的完整生成；不将超厚候选当薄解。',
        'scope': '阶段课程验收，不是任意目标可解性证明；来源外专家表现单独报告，不将同源目标组合写成跨原理能力。',
    })
    write_json(ROOT/'rejected.json', [{'id': r['id'], 'reason': r['evaluation']['reason']} for r in rejected])
    write_json(ROOT/'manifest.json', {'examples': len(records), 'new_accepted': len(accepted), 'new_rejected': len(rejected),
        'counts': dict(Counter(r['usage']+'/'+r['family'] for r in records)),
        'development': dict(Counter(r['family']+'/'+str(len(r['task']['targets'])) for r in development)),
        'heldout': dict(Counter(r['family']+'/'+str(len(r['task']['targets'])) for r in heldout)),
        'data_digest': digest((ROOT/'examples.jsonl').read_text()), 'seconds': time.monotonic()-started})
    print((ROOT/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

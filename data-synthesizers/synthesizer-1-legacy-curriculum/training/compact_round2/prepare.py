"""冻结目标组合的使用用途，再逐条制作完整运行标签。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
import time
from pathlib import Path

from ..compact.transforms import transform
from ..compact.run import choose
from ..compact.mechanisms import analyze
from ..data import read_examples
from ..evaluator import evaluate
from ..prepare import simulate_example
from ..serialization import digest, write_json
from .config import DATA, PLAN
from .rules import diagonal_strong, geometry, mixed_rules


def verify(row):
    row = simulate_example(row)
    if row['evaluation']['accepted'] and row['family'].startswith('mixed_'):
        proof = evaluate(row['task'], row['proposal'], True)
        evidence = analyze(proof['trace'])
        row['mechanisms'] = evidence
        if not evidence['mixed_boundaries_separated_in_motion'] or not evidence['nonempty_pull_operations']:
            row['evaluation'].update(accepted=False, reason='未观察到相邻异材分别运动或非空回拉')
    return row


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    if (DATA/'manifest.json').exists():
        raise ValueError('已有冻结数据，不覆盖；新的实验请使用新目录')
    started = time.monotonic()
    old = read_examples('data/generation/stage3/examples.jsonl')
    experts = json.loads(Path('data/generation/stage1/expert-snapshot.json').read_text())
    seen = {geometry(r['task']) for r in old}
    for path in ('data/generation/stage3/five-target-heldout.jsonl', 'data/generation/stage2/heldout.jsonl'):
        if Path(path).exists():
            seen.update(geometry(r['task']) for r in read_examples(path))
    prototypes = [r for r in [*mixed_rules(experts), *diagonal_strong()] if geometry(r['task']) not in seen]
    assignment = {}
    for family in sorted({r['family'] for r in prototypes}):
        groups = sorted({geometry(r['task']) for r in prototypes if r['family'] == family},
                        key=lambda g: digest(['round2_split', g]))
        held = max(1, len(groups)//6)
        for i, group in enumerate(groups):
            assignment[group] = 'development' if i < held else 'new_combination' if i < held*2 else 'fit'
    candidates = []
    for row in prototypes:
        row['geometry'] = geometry(row['task'])
        row['usage'] = assignment[row['geometry']]
        for swap, sx, sy, materials in ((False, 1, 1, False), (True, 1, 1, False),
                                         (False, -1, 1, True), (True, -1, -1, True)):
            candidates.append(transform(row, swap, sx, sy, materials))
    candidates = list({r['id']: r for r in candidates}.values())
    write_json(DATA/'allocation.json', {'geometry_usage': assignment, 'plan': PLAN,
        'prototype_count': len(prototypes), 'candidate_count': len(candidates)})
    accepted, rejected = [], []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for i, row in enumerate(pool.map(verify, candidates, chunksize=4)):
            (accepted if row['evaluation']['accepted'] else rejected).append(row)
            if (i+1) % 100 == 0:
                print(json.dumps({'已制作': i+1, '有效': len(accepted), '总数': len(candidates)}, ensure_ascii=False), flush=True)
    old_train = [{**r, 'usage': 'fit', 'geometry': geometry(r['task'])} for r in old if r['split'] == 'train']
    records = [*old_train, *accepted]
    fit_geometry = {r['geometry'] for r in records if r['usage'] == 'fit'}
    if any(r['geometry'] in fit_geometry for r in records if r['usage'] != 'fit'):
        raise ValueError('新组合的目标几何与拟合集合交叉')
    development, heldout = [], []
    for family in ('mixed_two', 'mixed_three', 'strong_compact'):
        for usage, output, limit in (('development', development, 8), ('new_combination', heldout, 12)):
            rows = [{**r, 'group': r['geometry']} for r in accepted if r['family'] == family and r['usage'] == usage]
            if not rows:
                raise ValueError('评估课程为空：'+family+'/'+usage)
            selected = choose(rows, limit)
            # 来源编号另存，评估器的group表示目标几何组合而非独立设计来源。
            by_id = {r['id']: r for r in accepted}
            output.extend({**r, 'source_group': by_id[r['id']]['group'], 'split': 'validation' if usage == 'development' else 'test'} for r in selected)
    # 拉驱只有训练来源，选模中明确作为能力保持诊断。
    pulls = choose([r for r in old_train if r['family'] == 'pull_compact'], 8)
    development.extend({**r, 'split': 'validation', 'usage': 'training_diagnostic'} for r in pulls)
    write_rows(DATA/'examples.jsonl', records)
    write_rows(DATA/'development.jsonl', development)
    write_rows(DATA/'heldout.jsonl', heldout)
    write_json(DATA/'rejected.json', [{'id': r['id'], 'family': r['family'], 'reason': r['evaluation']['reason']} for r in rejected])
    write_json(DATA/'experiment-plan.json', PLAN)
    write_json(DATA/'manifest.json', {'examples': len(records), 'new_accepted': len(accepted), 'new_rejected': len(rejected),
        'counts': dict(Counter(r['usage']+'/'+r['family'] for r in records)),
        'development': dict(Counter(r['family'] for r in development)), 'heldout': dict(Counter(r['family'] for r in heldout)),
        'data_digest': digest((DATA/'examples.jsonl').read_text()), 'seconds': time.monotonic()-started,
        'scope': PLAN['scope'], 'expert_sources': ['移动线7', '移动线13', '移动线15']})
    print((DATA/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

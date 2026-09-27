"""固定长路径输出组合补强的数据版本与分族采样计划。"""

from collections import Counter
import json
from pathlib import Path
import shutil

from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..data import read_examples
from ..serialization import digest, write_json


def main():
    root = Path('data/generation/stage4-combinations')
    if (root/'manifest.json').exists():
        raise ValueError('组合课程已冻结')
    root.mkdir(parents=True, exist_ok=True)
    base = Path('data/generation/stage4-balanced')
    addition = Path('data/generation/stage4-output-combinations')
    summary = json.loads((addition/'manifest.json').read_text())
    assert summary['reserved_geometry_overlap'] == summary['reserved_group_overlap'] == 0
    rows = read_examples(base/'examples.jsonl') + read_examples(addition/'examples.jsonl')
    unique = {r['id']: r for r in rows}
    rows = list(unique.values())
    fit_geometry = {geometry(r['task']) for r in rows if r['usage'] == 'fit'}
    old_development = read_examples(base/'development.jsonl')
    overlapping = [r for r in old_development if geometry(r['task']) in fit_geometry]
    development = [r for r in old_development if geometry(r['task']) not in fit_geometry]
    # 已训练过的需求保留作复查，不混入独立开发选模；按固定排序补足未用开发骨架。
    selected_groups = {r['group'] for r in development if r['family'].startswith('path_')}
    counts = Counter(r['family'] for r in development)
    for row in sorted(rows, key=lambda r: digest(['expanded_development', r['id']])):
        family = row['family']
        if row['usage'] != 'development' or family not in ('path_varied', 'path_four'):
            continue
        if row['group'] in selected_groups or counts[family] >= (8 if family == 'path_varied' else 12):
            continue
        development.append(row)
        selected_groups.add(row['group'])
        counts[family] += 1
    reserved = [r for r in rows if r['usage'] != 'fit'] + development
    for name in ('heldout', 'fresh'):
        reserved += read_examples(base/(name+'.jsonl'))
    assert not fit_geometry & {geometry(r['task']) for r in reserved}
    for name in ('heldout.jsonl', 'retention.jsonl', 'thickness.jsonl',
                 'fresh.jsonl', 'fresh-plan.json', 'stage-goals.json', 'evaluation-plan.json',
                 'frozen.json', 'split-audit.json', 'balanced-split-audit.json'):
        shutil.copyfile(base/name, root/name)
    write_rows(root/'development.jsonl', development)
    write_rows(root/'seen-development-rechecks.jsonl', overlapping)
    # 长路径按每组输出数量均衡，避免新增样本再次改变需求难度分布。
    for row in rows:
        if row['family'] in ('path_varied', 'path_four'):
            count = len(row['task']['targets'])
            orders = len({t['order'] for t in row['task']['targets']})
            row['sampling_group'] = 'sparse' if count <= orders+1 else 'medium' if count <= 2*orders else 'dense'
    write_rows(root/'examples.jsonl', rows)
    plan = json.loads((base/'experiment-plan.json').read_text())
    plan.update(initial_checkpoint='runs/stage4-balanced/best.pt', steps=24000, seed=20261007,
                learning_rate=.000035)
    write_json(root/'experiment-plan.json', plan)
    write_json(root/'manifest.json', {'data_digest': digest((root/'examples.jsonl').read_text()),
        'fit_counts': dict(Counter(r['family'] for r in rows if r['usage'] == 'fit')),
        'new_output_examples': summary['accepted'],
        'development_counts': dict(counts),
        'seen_development_rechecks': len(overlapping),
        'fit_reserved_geometry_overlap': 0,
        'path_sampling': dict(Counter(r['family']+'/'+r['sampling_group'] for r in rows
                                     if r['usage'] == 'fit' and r['family'].startswith('path_'))),
        'scope': '补充已有训练机械路径的输出端组合；原评估和验收阈值全部保留。'})
    print((root/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

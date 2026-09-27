"""恢复旧课程分族采样，防止少量专家骨架被大量几何组挤占。"""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil

from ..compact_round2.prepare import write_rows
from ..data import read_examples
from ..serialization import digest, write_json


def main():
    root = Path('data/generation/stage4-balanced')
    if (root/'manifest.json').exists():
        raise ValueError('平衡课程已冻结')
    root.mkdir(parents=True, exist_ok=True)
    base = Path('data/generation/stage4-broader')
    original = read_examples('data/generation/stage3-balanced/examples.jsonl')
    by_id = {r['id']: r['family'] for r in original}
    by_proposal = {digest(r['proposal']): r['family'] for r in original}
    rows = read_examples(base/'examples.jsonl')
    for row in rows:
        if row['family'] == 'retention':
            row['family'] = 'old_'+by_id[row['id']]
        elif row['family'] == 'slack':
            row['sampling_group'] = by_proposal.get(digest(row['proposal']), 'new_paths')
    development = [r for r in read_examples(base/'development.jsonl') if r['family'] != 'retention']
    old_development = read_examples('data/generation/stage3-balanced/development.jsonl')
    for row in old_development:
        row['family'] = 'old_'+row['family']
    development += old_development
    for name in ('heldout.jsonl', 'retention.jsonl', 'thickness.jsonl', 'fresh.jsonl', 'fresh-plan.json',
                 'stage-goals.json', 'evaluation-plan.json', 'frozen.json', 'split-audit.json'):
        shutil.copyfile(base/name, root/name)
    write_rows(root/'examples.jsonl', rows)
    write_rows(root/'development.jsonl', development)
    plan = json.loads((base/'experiment-plan.json').read_text())
    plan.update(initial_checkpoint='runs/stage4-refine/best.pt', steps=24000, seed=20261006,
        learning_rate=.000045, family_sampling={'old_legacy_parallel': .04, 'old_legacy_relay': .01,
        'old_mixed_three': .14, 'old_mixed_two': .08, 'old_strong_compact': .07,
        'old_strong_wide': .04, 'old_expert_compact': .035, 'old_pull_compact': .025,
        'old_strong_staggered': .01, 'slack': .10, 'path_varied': .10, 'path_four': .20, 'dense': .05})
    write_json(root/'experiment-plan.json', plan)
    write_json(root/'manifest.json', {'data_digest': digest((root/'examples.jsonl').read_text()),
        'fit_counts': dict(Counter(r['family'] for r in rows if r['usage'] == 'fit')),
        'development_counts': dict(Counter(r['family'] for r in development)),
        'sampling': plan['family_sampling'], 'reason': '旧课程恢复分族采样；原先合并后的均匀几何组采样稀释了少数混材骨架。',
        'scope': '首批42需求已查看，继续作为扩展回归；另32需求保持未评估，各自泛化口径见fresh-plan。'})
    print((root/'manifest.json').read_text())


if __name__ == '__main__':
    main()

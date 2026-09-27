"""为已有训练路径补充不同输出端组合，完整机械连接保持原构造。"""

from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path
import random

from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..data import read_examples
from ..prepare import simulate_example
from ..serialization import digest, write_json


def main():
    root = Path('data/generation/stage4-output-combinations')
    if (root/'manifest.json').exists():
        raise ValueError('输出组合已冻结，不覆盖')
    root.mkdir(parents=True, exist_ok=True)
    base = Path('data/generation/stage4-balanced')
    rows = read_examples(base/'examples.jsonl')
    reserved = [r for r in rows if r['usage'] != 'fit']
    for name in ('development', 'heldout', 'fresh', 'retention', 'thickness'):
        reserved += read_examples(base/(name+'.jsonl'))
    excluded = {geometry(r['task']) for r in reserved}
    excluded_groups = {r['group'] for r in reserved if r['family'].startswith('path_')}
    seen = {digest([r['task'], r['proposal']]) for r in rows}
    candidates = []
    for row in read_examples('data/generation/stage4-augmentation/examples.jsonl'):
        if row['usage'] != 'fit' or row['group'] in excluded_groups:
            continue
        groups = defaultdict(list)
        for target in row['task']['targets']:
            groups[target['order']].append(target)
        rng = random.Random(int(digest(['output_combinations', row['id']])[:12], 16))
        for mode in ('single', 'pair', 'varied'):
            chosen = []
            for targets in groups.values():
                count = 1 if mode == 'single' else min(2, len(targets)) if mode == 'pair' else rng.randint(1, len(targets))
                chosen += rng.sample(targets, count)
            copy = deepcopy(row)
            copy['task']['targets'] = sorted(chosen, key=lambda t: (t['x'], t['y']))
            omit = {(t['x'], t['y'], -2) for t in row['task']['targets'] if t not in chosen}
            copy['proposal']['blocks'] = [b for b in copy['proposal']['blocks']
                if tuple(b['position'][a] for a in ('x', 'y', 'z')) not in omit]
            key = digest([copy['task'], copy['proposal']])
            if geometry(copy['task']) in excluded or key in seen:
                continue
            seen.add(key)
            copy['output_selection'] = mode
            candidates.append(copy)
    write_json(root/'allocation.json', {'candidates': len(candidates), 'digest': digest(candidates),
        'method': '每个时序组选择一、二或可变数量输出端；保留供电与回拉连接，重新确认十负载三轮。'})
    accepted, rejected = [], []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for i, row in enumerate(pool.map(simulate_example, candidates, chunksize=4), 1):
            (accepted if row['evaluation']['accepted'] else rejected).append(row)
            if i % 300 == 0:
                print({'已确认': i, '有效': len(accepted)}, flush=True)
    write_rows(root/'examples.jsonl', accepted)
    write_rows(root/'rejected.jsonl', rejected)
    write_json(root/'manifest.json', {'accepted': len(accepted), 'rejected': len(rejected),
        'families': dict(Counter(r['family'] for r in accepted)),
        'groups': len({r['group'] for r in accepted}),
        'reserved_geometry_overlap': len({geometry(r['task']) for r in accepted} & excluded),
        'reserved_group_overlap': len({r['group'] for r in accepted} & excluded_groups),
        'data_digest': digest((root/'examples.jsonl').read_text()),
        'scope': '既有训练骨架的新输出端组合，不增加独立机械原理；未读取保留答案用于构造。'})
    print((root/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

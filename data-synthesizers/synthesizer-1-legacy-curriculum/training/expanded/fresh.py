"""补强训练前固定额外未查看需求，历史42条继续完整保留。"""

from collections import Counter
import json
from pathlib import Path
import random

from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..data import read_examples
from ..prepare import simulate_example
from ..serialization import digest, write_json
from .compact_dense import construct


def main():
    root = Path('data/generation/stage4-broader')
    if (root/'fresh.jsonl').exists():
        raise ValueError('额外保留需求已冻结')
    rows = read_examples(root/'examples.jsonl')
    old = read_examples(root/'heldout.jsonl')
    used = {geometry(r['task']) for r in old}
    used_groups = {r['group'] for r in old}
    all_geometries = {geometry(r['task']) for r in rows}
    selected = []
    for family, limit in [('path_varied', 12), ('path_four', 8)]:
        available = sorted([r for r in rows if r['usage'] == 'heldout' and r['family'] == family
                            and geometry(r['task']) not in used
                            and (family != 'path_four' or r['group'] not in used_groups)],
                           key=lambda r: digest(['stage4_fresh', r['id']]))
        counts = Counter()
        for row in available:
            if counts[row['group']] >= (3 if family == 'path_varied' else 1) or geometry(row['task']) in used:
                continue
            selected.append(row);counts[row['group']] += 1;used.add(geometry(row['task']))
            if sum(counts.values()) >= limit:
                break
    points = [(t['x'], t['y']) for t in construct()['task']['targets']]
    rng = random.Random(20261005)
    dense = []
    for attempt in range(1000):
        count = 12 if len(dense) < 6 else 15
        row = construct(rng.sample(points, count))
        key = geometry(row['task'])
        if key in all_geometries or key in used:
            continue
        row.update(usage='heldout', split='test', group=key)
        row = simulate_example(row)
        if row['evaluation']['accepted']:
            dense.append(row);used.add(key)
        if len(dense) >= 12:
            break
    selected += dense
    fit_geo = {geometry(r['task']) for r in rows if r['usage'] == 'fit'}
    dev_geo = {geometry(r['task']) for r in read_examples(root/'development.jsonl')}
    assert not {geometry(r['task']) for r in selected} & (fit_geo | dev_geo)
    write_rows(root/'fresh.jsonl', selected)
    write_json(root/'fresh-plan.json', {'counts': dict(Counter(r['family'] for r in selected)),
        'data_digest': digest((root/'fresh.jsonl').read_text()), 'minimum_family_rate': .75,
        'scope': {'path_varied': '已保留5个路径骨架中的全新目标组合，骨架此前已评估，答案未训练。',
                  'path_four': '此前未评估的8个完整路径骨架，与训练及开发骨架分离。',
                  'dense': '同一四格构造法内全新目标几何，与所有已有数据几何分离。'},
        'historical42': '原42条继续验收和对照，不删除失败，不再冒充首次独立评估。'})
    print((root/'fresh-plan.json').read_text())


if __name__ == '__main__':
    main()

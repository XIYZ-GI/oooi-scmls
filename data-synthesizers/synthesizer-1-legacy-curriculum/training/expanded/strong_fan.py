"""单个后层连接块带动三个供电中心，补充二格多方向同推课程。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path

from ..compact.curriculum import record
from ..compact.transforms import transform
from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..data import read_examples
from ..prepare import simulate_example
from ..serialization import digest, write_json
from ..templates import block


def main():
    root = Path('data/generation/stage4-strong-fan')
    if (root/'manifest.json').exists():
        raise ValueError('三中心课程已保存，不覆盖')
    root.mkdir(parents=True, exist_ok=True)
    base = Path('data/generation/stage4-accelerated')
    rows = read_examples(base/'examples.jsonl')
    reserved = [r for r in rows if r['usage'] != 'fit']
    for name in ('development', 'heldout', 'fresh', 'retention', 'thickness'):
        reserved += read_examples(base/(name+'.jsonl'))
    reserved += [r for r in read_examples('data/generation/stage3-balanced/examples.jsonl') if r['usage'] != 'fit']
    excluded = {geometry(r['task']) for r in reserved}
    seen = {digest([r['task'], r['proposal']]) for r in rows}
    centers = [(1, 2), (2, 1), (3, 2)]
    outputs = sorted({(x+dx, y+dy) for x, y in centers for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]})
    candidates = []
    for count in (3, 4, 5):
        for selected in combinations(outputs, count):
            blocks = [block(x, y, z, kind) for x, y in centers for z, kind in [(-3, 'observer'), (-2, 'slime_block')]]
            blocks += [block(2, 2, -3, 'slime_block')]
            blocks += [block(x, y, -2, 'piston') for x, y in selected]
            row = record(blocks, dict(x=2, y=2, z=-3),
                         [dict(x=x, y=y, z=0, order=1) for x, y in selected], 'old_strong_compact', split='train')
            if geometry(row['task']) in excluded:
                continue
            row.update(usage='fit', source='three_center_strong_fan_v1')
            for swap, sx, sy, material in [(False, 1, 1, False), (True, 1, 1, False),
                                           (False, -1, 1, True), (True, -1, -1, True)]:
                copy = transform(row, swap, sx, sy, material)
                key = digest([copy['task'], copy['proposal']])
                if key not in seen:
                    seen.add(key);candidates.append(copy)
    accepted, rejected = [], []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for row in pool.map(simulate_example, candidates, chunksize=4):
            (accepted if row['evaluation']['accepted'] else rejected).append(row)
    write_rows(root/'examples.jsonl', accepted)
    write_rows(root/'rejected.jsonl', rejected)
    write_json(root/'manifest.json', {'accepted': len(accepted), 'rejected': len(rejected),
        'target_counts': dict(Counter(len(r['task']['targets']) for r in accepted)),
        'reserved_geometry_overlap': len({geometry(r['task']) for r in accepted} & excluded),
        'data_digest': digest((root/'examples.jsonl').read_text()),
        'scope': '三中心二格强充能，整个初始结构10至12块；三轮十负载完整确认，不是独立人工来源。'})
    print((root/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

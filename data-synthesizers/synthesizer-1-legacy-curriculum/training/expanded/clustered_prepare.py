"""准备同刻多中心、组间拉驱的完整课程，并排除所有保留几何。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path
import random

from ..compact.transforms import transform
from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..data import read_examples
from ..prepare import simulate_example
from ..serialization import digest, write_json
from .clustered import clustered_line


def main():
    root = Path('data/generation/stage4-clustered')
    if (root/'manifest.json').exists():
        raise ValueError('已有分组拉驱课程，不覆盖')
    root.mkdir(parents=True, exist_ok=True)
    base = Path('data/generation/stage4-accelerated')
    rows = read_examples(base/'examples.jsonl')
    reserved = [r for r in rows if r['usage'] != 'fit']
    for name in ('development', 'heldout', 'fresh', 'retention', 'thickness'):
        reserved += read_examples(base/(name+'.jsonl'))
    reserved += [r for r in read_examples('data/generation/stage3-balanced/examples.jsonl') if r['usage'] != 'fit']
    excluded = {geometry(r['task']) for r in reserved}
    seen = {digest([r['task'], r['proposal']]) for r in rows}
    candidates = []
    rng = random.Random(20261011)
    for sizes in ((1, 2), (2, 1), (2, 2), (1, 1, 2), (1, 2, 1), (2, 1, 1)):
        prototype = clustered_line(sizes)
        count = len(prototype['task']['targets'])
        choices = [c for size in range(len(sizes), count+1) for c in combinations(range(count), size)]
        rng.shuffle(choices)
        # 完整机械关系固定，只选择输出支路；每种分组最多512组，不做单块随机搜索。
        for selected in choices[:512]:
            try:
                row = clustered_line(sizes, selected)
            except ValueError:
                continue
            if geometry(row['task']) in excluded:
                continue
            for swap, sx, sy, materials in ((False, 1, 1, False), (True, 1, 1, False),
                                            (False, -1, 1, True), (True, -1, -1, True)):
                value = transform(row, swap, sx, sy, materials)
                key = digest([value['task'], value['proposal']])
                if key not in seen:
                    seen.add(key);candidates.append(value)
    accepted, rejected = [], []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for index, row in enumerate(pool.map(simulate_example, candidates, chunksize=8), 1):
            (accepted if row['evaluation']['accepted'] else rejected).append(row)
            if index % 500 == 0:
                print({'已制作': index, '总数': len(candidates), '有效': len(accepted)}, flush=True)
    write_rows(root/'examples.jsonl', accepted)
    write_rows(root/'rejected.jsonl', rejected)
    write_json(root/'manifest.json', {'accepted': len(accepted), 'rejected': len(rejected),
        'counts': dict(Counter(str(r['topology']['group_center_counts']) for r in accepted)),
        'target_counts': dict(Counter(len(r['task']['targets']) for r in accepted)),
        'reserved_geometry_overlap': len({geometry(r['task']) for r in accepted} & excluded),
        'data_digest': digest((root/'examples.jsonl').read_text()),
        'scope': '同刻多中心与组间拉驱的参数化组合，所有有效示范均通过三轮十负载。'})
    print((root/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

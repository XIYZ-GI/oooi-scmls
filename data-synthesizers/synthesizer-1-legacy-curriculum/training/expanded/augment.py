"""补充完整路径构造，排除已有开发与保留骨架及其目标几何。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from ..compact.transforms import transform
from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..data import read_examples
from ..prepare import simulate_example
from ..serialization import digest, write_json
from .prepare import prototypes


def main():
    root = Path('data/generation/stage4-augmentation')
    root.mkdir(parents=True, exist_ok=True)
    if (root/'manifest.json').exists():
        raise ValueError('补充课程已完成，不覆盖')
    base = read_examples('data/generation/stage4/examples.jsonl')
    reserved_groups = {r['group'] for r in base if r['usage'] != 'fit'}
    reserved_geometry = {geometry(r['task']) for r in base if r['usage'] != 'fit'}
    reserved_geometry.update(geometry(r['task']) for r in read_examples('data/generation/stage4/development.jsonl'))
    seen = {digest(r['proposal']) for r in base}
    candidates = []
    for row in prototypes(multiplier=3, seed=20261004):
        if row['group'] in reserved_groups or geometry(row['task']) in reserved_geometry or digest(row['proposal']) in seen:
            continue
        row.update(usage='fit', split='train')
        candidates.append(row)
    write_json(root/'allocation.json', {'candidates': len(candidates), 'excluded_groups': sorted(reserved_groups),
        'candidate_digest': digest(candidates), 'note': '未使用开发或保留答案；完整路径规则扩展，不执行随机单块修改。'})
    accepted, rejected = [], []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for i, row in enumerate(pool.map(simulate_example, candidates, chunksize=4)):
            (accepted if row['evaluation']['accepted'] else rejected).append(row)
            if (i+1) % 200 == 0:
                print({'已确认': i+1, '有效': len(accepted)}, flush=True)
    variants = [transform(row, swap=True, sx=-1, materials=True) for row in accepted]
    with ProcessPoolExecutor(max_workers=6) as pool:
        for row in pool.map(simulate_example, variants, chunksize=4):
            if row['evaluation']['accepted']:
                accepted.append(row)
    assert not {r['group'] for r in accepted} & reserved_groups
    assert not {geometry(r['task']) for r in accepted} & reserved_geometry
    write_rows(root/'examples.jsonl', accepted)
    write_rows(root/'rejected.jsonl', rejected)
    write_json(root/'manifest.json', {'examples': len(accepted), 'counts': dict(Counter(r['family'] for r in accepted)),
        'groups': len({r['group'] for r in accepted}), 'reserved_group_overlap': 0, 'reserved_geometry_overlap': 0,
        'data_digest': digest((root/'examples.jsonl').read_text())})
    print((root/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

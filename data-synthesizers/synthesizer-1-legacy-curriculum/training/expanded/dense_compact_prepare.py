"""将四格、同平面密集目标课程作为正式密集任务，六格方案仅归档。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import random
import shutil

from ..compact.transforms import transform
from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..prepare import simulate_example
from ..serialization import write_json, digest
from .compact_dense import construct


def main():
    root = Path('data/generation/stage4')
    archive = root/'six-layer-baseline'
    if archive.exists():
        raise ValueError('六格主课程已归档，不重复替换')
    archive.mkdir()
    for name in ('dense.jsonl', 'dense-manifest.json', 'frozen.json', 'split-audit.json', 'stage-goals.json', 'experiment-plan.json'):
        if (root/name).exists():
            shutil.copyfile(root/name, archive/name)
    # 撤销的是未训练的数据冻结；历史清单保存在对照目录。
    (root/'frozen.json').unlink()
    options = [(t['x'], t['y']) for t in construct()['task']['targets']]
    rng = random.Random(20261002)
    candidates = []
    for count in (12, 15, 18):
        combinations = {tuple(sorted(rng.sample(options, count))) for _ in range(120)}
        for chosen in sorted(combinations):
            row = construct(chosen)
            row['group'] = geometry(row['task'])
            bucket = int(digest(['stage4_compact_dense', row['group']])[:8], 16) % 10
            row['usage'] = 'development' if bucket == 0 else 'heldout' if bucket == 1 else 'fit'
            row['split'] = {'fit': 'train', 'development': 'validation', 'heldout': 'test'}[row['usage']]
            row['scope'] = '三个机械输出分组的同平面四格构造，按目标几何划分；两个时序，不能宣称同时推动。'
            candidates.extend(transform(row, sx=sx, sy=sy, materials=material) for sx, sy, material in
                              ((1, 1, False), (-1, 1, True), (1, -1, False), (-1, -1, True)))
    accepted, rejected = [], []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for row in pool.map(simulate_example, candidates, chunksize=4):
            (accepted if row['evaluation']['accepted'] else rejected).append(row)
    write_rows(root/'dense.jsonl', accepted)
    write_rows(root/'dense-rejected.jsonl', rejected)
    write_json(root/'dense-manifest.json', {'attempted': len(candidates), 'accepted': len(accepted),
        'counts': dict(Counter(r['usage'] for r in accepted)), 'depth': 4,
        'scope': '7×5截面，同一平面12或15或18目标，两组时序；全部三轮十负载验证。'})
    print((root/'dense-manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

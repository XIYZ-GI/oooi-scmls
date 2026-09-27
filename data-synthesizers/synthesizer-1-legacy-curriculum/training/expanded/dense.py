"""从训练来源移动线11制作密集目标课程，保留前后交错负载位置。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import random

from ..compact.transforms import transform
from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..data import read_examples
from ..prepare import simulate_example
from ..serialization import digest, write_json


def main():
    root = Path('data/generation/stage4')
    expert = next(r for r in json.loads(Path('data/generation/stage1/expert-snapshot.json').read_text()) if r['name'] == '移动线11')
    assert expert['split'] == 'train'
    targets = [{k: t[k] for k in ('x', 'y', 'z', 'order')} for t in expert['reference']['targets']]
    rng = random.Random(20261001)
    candidates = []
    for count in (12, 15, 18):
        for sample in range(100):
            chosen = sorted(rng.sample(targets, count), key=lambda t: (t['x'], t['y']))
            omitted = {(t['x'], t['y'], t['z']-2) for t in targets if t not in chosen}
            blocks = [deepcopy(b) for b in expert['request']['blocks'] if
                      tuple(b['position'][a] for a in ('x', 'y', 'z')) not in omitted]
            task = dict(width=7, height=5, depth=6, targets=chosen, max_ticks=48, rounds=3, load_blocks=10)
            group = geometry(task)
            bucket = int(digest(['stage4_dense', group])[:8], 16) % 10
            usage = 'development' if bucket == 0 else 'heldout' if bucket == 1 else 'fit'
            row = {'task': task, 'proposal': {'blocks': blocks, 'push': deepcopy(expert['request']['push_point'])},
                   'family': 'dense', 'group': group, 'source_group': 'expert-'+expert['group'],
                   'source': expert['id'], 'source_name': expert['name'], 'usage': usage,
                   'split': {'fit': 'train', 'development': 'validation', 'heldout': 'test'}[usage],
                   'scope': '训练成品骨架下的新目标组合，目标首块前后交错，不是任意平面15目标泛化。'}
            candidates += [transform(row), transform(row, sx=-1, materials=True)]
    accepted = []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for row in pool.map(simulate_example, candidates, chunksize=4):
            if row['evaluation']['accepted']:
                accepted.append(row)
    write_rows(root/'dense.jsonl', accepted)
    write_json(root/'dense-manifest.json', {'attempted': len(candidates), 'accepted': len(accepted),
        'counts': dict(Counter(r['usage'] for r in accepted)),
        'source': expert['name'], 'scope': '原训练来源骨架的输出组合，厚度6格，截面7×5，负载前后交错。'})
    print((root/'dense-manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()

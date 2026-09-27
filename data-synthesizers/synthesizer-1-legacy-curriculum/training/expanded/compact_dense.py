"""四格厚度的三级输出分组：左右双供电中心与中间单中心。"""

from ..templates import block
from ..serialization import digest


def construct(points=None):
    blocks = [block(x, 1, -5, 'slime_block') for x in range(1, 6)]
    for x in (1, 3, 5):
        observer = block(x, 0, -5, 'observer')
        observer['block']['facing'] = 'positive_y'
        blocks.extend([observer, block(x, 2, -5, 'piston')])
    hubs = [(1, 1), (1, 3), (5, 1), (5, 3), (3, 2)]
    for x, y in hubs:
        blocks.extend([block(x, y, -3, 'observer'), block(x, y, -2, 'slime_block')])
    blocks.extend([block(x, 2, -3, 'slime_block') for x in (1, 5)])
    options = sorted({(x+dx, y+dy) for x, y in hubs for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))})
    points = options if points is None else sorted(points)
    blocks.extend(block(x, y, -2, 'piston') for x, y in points)
    later = {(0, 3), (1, 4), (2, 3), (4, 3), (5, 4), (6, 3)}
    task = dict(width=7, height=5, depth=4, targets=[dict(x=x, y=y, z=0, order=2 if (x, y) in later else 1) for x, y in points],
                max_ticks=32, rounds=3, load_blocks=10)
    return {'task': task, 'proposal': {'blocks': blocks, 'push': dict(x=3, y=1, z=-5)},
            'family': 'dense', 'source': 'compact_dense_three_groups_v1', 'group': digest(task), 'split': 'train'}

"""从实际几何关系枚举供电位置，区分活塞推出端和可接收端。"""

from collections import defaultdict

from .config import CONDUCTORS, VECTORS
from .geometry import add


def sockets(blocks, observers=None):
    found = defaultdict(set)
    origins = blocks if observers is None else observers
    for p in origins:
        spec = blocks[p]
        if spec['kind'] != 'observer':
            continue
        direction = VECTORS[spec['facing']]
        q = add(p, direction)
        if q not in blocks:
            if direction != (0, 0, -1):
                found[q].add('push')
            if direction != (0, 0, 1):
                found[q].add('pull')
        if blocks.get(q, {}).get('kind') not in CONDUCTORS:
            continue
        for d in VECTORS.values():
            cell = add(q, d)
            if cell in blocks:
                continue
            if d != (0, 0, -1):
                found[cell].add('push')
            if d != (0, 0, 1):
                found[cell].add('pull')
    return dict(found)

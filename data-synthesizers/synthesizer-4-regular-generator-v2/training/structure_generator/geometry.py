"""坐标运算与平移、横截面对称等价指纹。"""

from itertools import product

from ..serialization import digest
from .config import AXES, VECTORS, FACING


def point(value):
    return tuple(value[a] for a in AXES)


def position(value):
    return dict(zip(AXES, value))


def add(a, b, scale=1):
    return tuple(x + scale*y for x, y in zip(a, b))


def canonical(blocks, targets=()):
    """忽略平移、截面对称与粘液蜂蜜整体互换，保留纵深和时序。"""
    keys = []
    for swap, sx, sy, materials in product((False, True), (-1, 1), (-1, 1), (False, True)):
        def transform(p):
            x, y, z = p
            return sx*(y if swap else x), sy*(x if swap else y), z
        raw = [(transform(point(b['position'])), b['block']) for b in blocks]
        offset = tuple(min(p[i] for p, _ in raw) for i in range(3))
        cells = []
        for p, spec in raw:
            kind = spec['kind']
            if materials:
                kind = {'slime_block': 'honey_block', 'honey_block': 'slime_block'}.get(kind, kind)
            facing = (FACING[transform(VECTORS[spec['facing']])]
                      if kind in ('observer', 'piston', 'sticky_piston') else 'positive_z')
            cells.append((*add(p, offset, -1), kind, facing))
        outputs = [(*add(transform(point(t)), offset, -1), t['order']) for t in targets]
        keys.append(digest([sorted(cells), sorted(outputs)]))
    return min(keys)

"""在后层随机布置同刻推驱接口及回拉接口，供前层实心输出区组合。"""

from .config import FACING, MATERIALS, SIDES
from .geometry import add


def supply(layout, rng, anchor, request):
    saved = layout.checkpoint()
    axis = rng.choice(SIDES)
    normal = rng.choice([d for d in SIDES if sum(a*b for a, b in zip(axis, d)) == 0])
    pushes = sum(kind == 'push' for kind, _ in request['children'])
    width = rng.choice((1, 1, 2)) if pushes >= 2 else rng.choice((1, 2))
    if pushes >= 3:
        # 单个供电中心只有两个后层侧向空位，三分支需两个相邻中心。
        width = 2
    offset, material = rng.randrange(width), rng.choice(MATERIALS)
    charges = []
    for index in range(width):
        charge = add(anchor, tuple(v*(index-offset) for v in axis))
        observer = add(charge, normal)
        if not layout.put(charge, material) or not layout.put(observer, 'observer', FACING[tuple(-v for v in normal)]):
            layout.restore(saved)
            return None
        charges.append(charge)
    support = rng.choice(charges)
    extension = add(support, tuple(-v for v in normal))
    if not layout.put(extension, material):
        layout.restore(saved)
        return None
    observer = add(extension, tuple(-v for v in normal))
    charge = add(observer, (0, 0, 1))
    if not layout.put(observer, 'observer') or not layout.put(charge, material):
        layout.restore(saved)
        return None
    charges.append(charge)
    added = set(layout.blocks)-set(saved[0])
    first, last = charges[0], charges[-2]
    preferred = [add(first, tuple(-v for v in axis)), add(last, axis)]
    layout.operations.append(dict(kind='分层随机推拉供电排', anchor=anchor,
                                  charges=charges, added=sorted(added), preferred_pushes=preferred,
                                  strip_axis=axis))
    return added

"""从随机侧向路径生长相邻供电中心，观察者的黏性支撑位于旁边。"""

from .config import MATERIALS, SIDES
from .geometry import add


def supply(layout, rng, anchor, budget=8):
    saved = layout.checkpoint()
    material = rng.choice(MATERIALS)
    if not layout.put(anchor, material):
        return None
    directions = list(SIDES)
    rng.shuffle(directions)
    # 支撑轴及供电中心数量均随机；一至两个中心可形成连续的共享输出区域。
    axis = rng.choice(SIDES)
    count = rng.choice((1, 2, 2))
    charges = []
    for index in range(count):
        support = add(anchor, tuple(v*index for v in axis))
        if index and not layout.put(support, material):
            break
        for direction in directions:
            if sum(a*b for a, b in zip(direction, axis)):
                continue
            observer = add(support, direction)
            charge = add(observer, (0, 0, 1))
            if not layout.free(observer) or not layout.free(charge):
                continue
            if not layout.put(observer, 'observer') or not layout.put(charge, material):
                layout.restore(saved)
                return None
            charges.append(charge)
            break
        else:
            break
    added = set(layout.blocks)-set(saved[0])
    if not charges or len(added) > budget:
        layout.restore(saved)
        return None
    layout.operations.append(dict(kind='侧置连续供电', anchor=anchor,
                                  charges=charges, added=sorted(added)))
    return added

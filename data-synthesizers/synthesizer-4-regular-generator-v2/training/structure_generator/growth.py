"""通过材料延伸和观察者放置，在全局布局中生长供电几何。"""

from .config import FACING, MATERIALS, SIDES, VECTORS
from .geometry import add


def observer_for(layout, rng, charge, lateral=True, compact=False):
    choices = list(SIDES)
    rng.shuffle(choices)
    if not lateral:
        choices = [(0, 0, -1), *choices, (0, 0, 1)]
    if compact:
        def area(offset):
            points = [*layout.blocks, add(charge,offset)]
            return (max(p[0] for p in points)-min(p[0] for p in points)+1)*(
                    max(p[1] for p in points)-min(p[1] for p in points)+1)
        choices.sort(key=area)
    for offset in choices:
        p = add(charge, offset)
        if layout.put(p, 'observer', FACING[tuple(-v for v in offset)]):
            return p
    return None


def supply(layout, rng, anchor, style, budget=8, compact=False):
    """每次从受推或受拉的位置生成方块，不读取预制单元库。"""
    before = set(layout.blocks)
    material = rng.choice(MATERIALS)
    if not layout.put(anchor, material):
        return None
    charges = []
    if style in ('前置供电', '入口延伸'):
        sides = list(SIDES)
        rng.shuffle(sides)
        for d in sides:
            observer = add(anchor, d)
            charge = add(observer, (0, 0, 1))
            if layout.free(observer) and layout.free(charge):
                layout.put(observer, 'observer', 'positive_z')
                layout.put(charge, material)
                charges.append(charge)
                break
        if not charges:
            return None
    else:
        charges.append(anchor)

    # 横向生长的每个末端都有自己的供电用途；连接块仅用于到达该末端。
    steps = rng.choice((0, 1, 1) if compact else (0, 1, 1, 2, 3)) if style == '共享供电片' else 0
    materials = [anchor]
    for _ in range(steps):
        options = [(p, d) for p in materials for d in SIDES]
        rng.shuffle(options)
        for p, d in options:
            q = add(p, d)
            if layout.put(q, material):
                materials.append(q)
                charges.append(q)
                break

    if style == '入口延伸':
        directions = list(SIDES)
        rng.shuffle(directions)
        for d in directions:
            path = [add(anchor, d)]
            if rng.random() < .3:
                path.append(add(path[-1], d))
            # 前置接口适合两格；保留入口纵深的接口可向后扩展到三格。
            if rng.random() < .55:
                path.append(add(path[-1], (0, 0, 1)))
            if len(set(path)) == len(path) and all(layout.free(p) for p in path):
                for p in path:
                    layout.put(p, material)
                charges.append(path[-1])
                break
        else:
            return None

    for charge in charges:
        powered = any(b['kind'] == 'observer' and add(p, VECTORS[b['facing']]) == charge
                      for p, b in layout.blocks.items())
        if not powered and observer_for(layout, rng, charge, lateral=rng.random() < .85, compact=compact) is None:
            return None
    added = set(layout.blocks)-before
    if len(added) > budget:
        return None
    layout.operations.append(dict(kind=style, anchor=anchor, charges=charges, added=sorted(added)))
    return added

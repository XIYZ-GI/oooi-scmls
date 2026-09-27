"""从前层回拉入口向后层侧向生长供电，保持总厚度四格。"""

from .config import FACING, MATERIALS, SIDES
from .geometry import add


def supply(layout, rng, anchor):
    saved = layout.checkpoint()
    material = rng.choice(MATERIALS)
    axis = rng.choice(SIDES)
    normal = rng.choice([d for d in SIDES if sum(a*b for a, b in zip(axis, d)) == 0])
    # 入口在后层前片，沿侧面接到后一片，观察者继续用旁侧支撑。
    support = add(anchor, axis)
    rear = add(support, (0, 0, -1))
    for p in (anchor, support, rear):
        if not layout.put(p, material):
            layout.restore(saved)
            return None
    observer = add(rear, normal)
    if not layout.put(observer, 'observer', FACING[tuple(-v for v in normal)]):
        layout.restore(saved)
        return None
    # 需要同层回拉时，入口片也可独立供电，不依赖额外纵深。
    if rng.random() < .5:
        upper_observer = add(anchor, tuple(-v for v in normal))
        if layout.free(upper_observer):
            layout.put(upper_observer, 'observer', FACING[normal])
    added = set(layout.blocks)-set(saved[0])
    layout.operations.append(dict(kind='跨层回拉侧置供电', anchor=anchor,
                                  charges=[rear, anchor], added=sorted(added)))
    return added

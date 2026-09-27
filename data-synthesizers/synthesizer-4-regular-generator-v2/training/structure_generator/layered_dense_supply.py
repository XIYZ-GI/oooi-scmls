"""在四格总厚度内交错放置供电组，给同刻输出预留完整三排区域。"""

from .config import MATERIALS, SIDES
from .geometry import add


def supply(layout, rng, anchor, axis=None):
    saved = layout.checkpoint()
    material, axis = rng.choice(MATERIALS), axis or rng.choice(SIDES)
    normal = rng.choice([d for d in SIDES if sum(a*b for a, b in zip(axis, d)) == 0])
    # 入口置于排端，避开后方推驱正面，不能让推驱直接碰观察者侦测面。
    if not layout.put(anchor, material):
        return None
    charges, outputs = [], []
    for index in (1, 2):
        charge = add(anchor, tuple(v*index for v in axis))
        observer = add(charge, (0, 0, -1))
        if not layout.put(charge, material) or not layout.put(observer, 'observer'):
            layout.restore(saved)
            return None
        charges.append(charge)
        outputs.extend((add(charge, (0, 0, 1)), add(charge, normal),
                        add(charge, tuple(-v for v in normal))))
    occupied = {v['piston'][:2] for v in layout.outputs}
    if any(not layout.free(p) or p[:2] in occupied for p in outputs):
        layout.restore(saved)
        return None
    added = set(layout.blocks)-set(saved[0])
    layout.operations.append(dict(kind='分层交错三排供电', anchor=anchor, charges=charges,
                                  added=sorted(added), preferred_outputs=outputs))
    return added

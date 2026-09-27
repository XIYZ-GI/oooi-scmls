"""在随机接口旁生长同向充能短排，为同刻双行实心输出预留位置。"""

from .config import FACING, MATERIALS, SIDES
from .geometry import add
from ..regular_generator_v2.rectangles import rectangles


def supply(layout, rng, anchor, width_limit=None):
    saved = layout.checkpoint()
    axis = rng.choice(SIDES)
    normal = rng.choice([d for d in SIDES if sum(a*b for a, b in zip(axis, d)) == 0])
    pulled = add(anchor, (0, 0, 1)) in layout.blocks
    width = 2 if pulled else rng.choice((2, 3, 3))
    if width_limit is not None:
        width = min(width, width_limit)
    offset = -1 if pulled else rng.randrange(width)
    material = rng.choice(MATERIALS)
    charges, outputs = [], []
    # 回拉接口前方已有驱动活塞；把入口放在短排端外，不能占用实心输出列。
    if pulled and not layout.put(anchor, material):
        return None
    for index in range(width):
        charge = add(anchor, tuple(v*(index-offset) for v in axis))
        observer = add(charge, normal)
        if not layout.put(charge, material) or not layout.put(observer, 'observer', FACING[tuple(-v for v in normal)]):
            layout.restore(saved)
            return None
        charges.append(charge)
        outputs.extend((add(charge, (0, 0, 1)), add(charge, tuple(-v for v in normal))))
    existing = {v['piston'][:2] for v in layout.outputs}
    if any(not layout.free(p) or p[:2] in existing for p in outputs):
        layout.restore(saved)
        return None
    added = set(layout.blocks)-set(saved[0])
    layout.operations.append(dict(kind='分层同向充能短排', anchor=anchor, charges=charges,
                                  added=sorted(added), preferred_outputs=outputs))
    return added


def guided_supply(layout, rng, anchor, tick):
    """随机采样不同方向和长度，优先与同刻输出拼成完整矩形。"""
    saved = layout.checkpoint()
    points = {v['piston'][:2] for v in layout.outputs if v['tick'] == tick}
    best, best_score, best_added = None, None, None
    for _ in range(12):
        layout.restore(saved)
        added = supply(layout, rng, anchor)
        if not added:
            continue
        outputs = layout.operations[-1]['preferred_outputs']
        combined = points | {p[:2] for p in outputs}
        regions = rectangles(combined)
        body = {p[:2] for p in layout.blocks} | combined
        xs, ys = zip(*body)
        area = (max(xs)-min(xs)+1)*(max(ys)-min(ys)+1)
        quality = (regions[0]['area'] if regions else 0, len(combined)/area)
        if best_score is None or quality > best_score:
            best, best_score, best_added = layout.checkpoint(), quality, added
    layout.restore(best if best is not None else saved)
    return best_added

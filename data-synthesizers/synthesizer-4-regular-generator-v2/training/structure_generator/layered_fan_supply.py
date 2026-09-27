"""按目标矩形间距生长随机后层供电排，保留原搜索的分支回退。"""

from .config import FACING, MATERIALS, SIDES
from .geometry import add


def supply(layout, rng, anchor, request):
    saved = layout.checkpoint()
    axis = rng.choice(SIDES)
    normal = rng.choice([d for d in SIDES if sum(a*b for a, b in zip(axis, d)) == 0])
    material = rng.choice(MATERIALS)
    centers = (0, 3)
    offset = rng.randrange(4)
    end_observers = request.get('end_observers')
    if end_observers is None:
        end_observers = rng.random() < .5
    charges, pushes = [], []
    for index in range(4):
        p = add(anchor, axis, index-offset)
        if not layout.put(p, material):
            layout.restore(saved)
            return None
        if index in centers:
            direction = axis if index == 0 else tuple(-v for v in axis)
            observer = add(p, direction, -1) if end_observers else add(p, normal, -1)
            if not layout.put(observer, 'observer', FACING[direction if end_observers else normal]):
                layout.restore(saved)
                return None
            charges.append(p)
            pushes.append(add(p, normal))
    if any(kind == 'pull' for kind, _ in request['children']):
        support = add(anchor, axis, rng.choice((1, 2))-offset)
        extension = add(support, normal)
        observer = add(extension, normal)
        charge = add(observer, (0, 0, 1))
        for p, kind, facing in ((extension, material, 'positive_z'),
                                (observer, 'observer', 'positive_z'),
                                (charge, material, 'positive_z')):
            if not layout.put(p, kind, facing):
                layout.restore(saved)
                return None
        charges.append(charge)
    for kind, child in request['children']:
        if kind == 'push':
            child['dense_axis'] = normal
    added = set(layout.blocks)-set(saved[0])
    layout.operations.append(dict(kind='随机矩形间距供电排', anchor=anchor,
                                  charges=charges, added=sorted(added), preferred_pushes=pushes))
    return added

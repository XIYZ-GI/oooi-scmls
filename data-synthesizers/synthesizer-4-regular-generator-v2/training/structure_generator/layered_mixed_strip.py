"""同推短排旁生长回拉接口，前层保留整片输出并继续拉动其他时序。"""

from .config import SIDES
from .geometry import add
from .layered_strip import supply as strip_supply


def supply(layout, rng, anchor):
    saved = layout.checkpoint()
    added = strip_supply(layout, rng, anchor, width_limit=2)
    if not added:
        return None
    operation = layout.operations[-1]
    outputs = set(operation['preferred_outputs'])
    options = [(p, direction) for p in operation['charges'] for direction in SIDES]
    rng.shuffle(options)
    for support, direction in options:
        observer = add(support, direction)
        charge = add(observer, (0, 0, 1))
        if observer in outputs or charge in outputs or not layout.free(observer) or not layout.free(charge):
            continue
        if not layout.put(observer, 'observer') or not layout.put(charge, layout.blocks[support]['kind']):
            layout.restore(saved)
            return None
        operation['charges'].append(charge)
        operation['added'].extend((observer, charge))
        operation['kind'] = '分层同推短排与侧置回拉'
        return added | {observer, charge}
    layout.restore(saved)
    return None

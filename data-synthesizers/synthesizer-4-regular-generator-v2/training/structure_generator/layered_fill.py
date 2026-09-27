"""利用后层现有供电的空闲推驱接口，填充前层空区并保留全部原目标。"""

from .geometry import add
from .power import sockets


def grow(search):
    layout, rng = search.layout, search.rng
    initial = len(layout.outputs)
    candidates = []
    for operation in layout.operations:
        if operation.get('layer') != 0:
            continue
        for driver, kinds in sockets(layout.blocks, operation['added']).items():
            entry = add(driver, (0, 0, 2))
            if ('push' in kinds and driver[2] == 0 and layout.free(driver) and layout.free(entry)
                    and driver[:2] not in {v['piston'][:2] for v in layout.outputs}):
                candidates.append((driver, entry, operation['tick']))
    rng.shuffle(candidates)
    for driver, entry, tick in candidates:
        if len(layout.outputs) >= 28 or search.simulations >= search.options.get('simulation_budget', 48):
            break
        saved = layout.checkpoint()
        if not layout.put(driver, 'piston'):
            continue
        layout.links.append(dict(kind='push', driver=driver, entry=entry, tick=tick))
        child = dict(layer=2, outputs=(2, 7), children=[])
        if not search.extend(child, entry, tick+4):
            layout.restore(saved)
    return len(layout.outputs)-initial

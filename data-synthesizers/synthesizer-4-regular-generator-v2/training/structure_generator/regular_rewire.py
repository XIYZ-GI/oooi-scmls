"""保留原目标及时序，随机重布观察者以腾出可供电的目标列。"""

from .config import FACING, VECTORS
from .density import fill
from .geometry import add


def improve(search):
    layout, rng = search.layout, search.rng
    initial = len(layout.outputs)
    candidates = []
    for index, operation in enumerate(layout.operations):
        for old in operation['added']:
            spec = layout.blocks.get(old, {})
            if spec.get('kind') != 'observer':
                continue
            charge = add(old, VECTORS[spec['facing']])
            if charge not in layout.blocks:
                continue
            for direction in VECTORS.values():
                new = add(charge, direction)
                if layout.free(new):
                    candidates.append((index, old, new, FACING[tuple(-v for v in direction)]))
    rng.shuffle(candidates)
    for index, old, new, facing in candidates:
        if search.simulations >= search.options.get('simulation_budget', 48):
            break
        if layout.blocks.get(old, {}).get('kind') != 'observer' or not layout.free(new):
            continue
        saved = layout.checkpoint()
        before = len(layout.outputs)
        del layout.blocks[old]
        if not layout.put(new, 'observer', facing):
            layout.restore(saved)
            continue
        operation = layout.operations[index]
        operation['added'] = [new if p == old else p for p in operation['added']]
        # fill 的每次预筛同时验证全部旧目标、旧标签以及修改后的整个本体。
        fill(search)
        if len(layout.outputs) == before:
            layout.restore(saved)
    return len(layout.outputs)-initial

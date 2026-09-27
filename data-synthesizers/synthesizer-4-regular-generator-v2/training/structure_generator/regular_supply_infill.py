"""沿既有随机骨架侧向补充前向供电，使空白目标列获得真实输出。"""

from .config import MATERIALS, SIDES
from .density import fill
from .geometry import add
from .power import sockets
from .regular_policy import prioritize
from .front_output import allowed as output_allowed


def grow(search):
    layout, rng = search.layout, search.rng
    candidates = []
    for index, operation in enumerate(layout.operations):
        for support in operation['added']:
            if layout.blocks.get(support, {}).get('kind') not in MATERIALS:
                continue
            for direction in SIDES:
                observer = add(support, direction)
                charge = add(observer, (0, 0, 1))
                if layout.free(observer) and layout.free(charge):
                    candidates.append((index, observer, charge, layout.blocks[support]['kind']))
    rng.shuffle(candidates)
    count = len(layout.outputs)
    for index, observer, charge, material in candidates:
        if search.simulations >= search.options.get('simulation_budget', 48) or len(layout.outputs) >= 32:
            break
        saved = layout.checkpoint()
        if not layout.put(observer, 'observer'):
            continue
        if not layout.put(charge, material):
            layout.restore(saved)
            continue
        positions = [p for p, kinds in sockets(layout.blocks, [observer]).items()
                     if 'push' in kinds and layout.free(p) and output_allowed(layout, p)
                     and p[:2] not in {v['piston'][:2] for v in layout.outputs}
                     and not any(q[:2] == p[:2] and q[2] > p[2] for q in layout.blocks)]
        rng.shuffle(positions)
        prioritize(positions, layout)
        powered = layout.checkpoint()
        accepted = False
        for p in positions:
            layout.restore(powered)
            if not layout.put(p, 'piston'):
                continue
            layout.outputs.append(dict(piston=p, tick=layout.operations[index]['tick']+4))
            if search.valid():
                layout.operations[index]['added'].extend((observer, charge))
                layout.operations[index]['charges'].append(charge)
                accepted = True
                fill(search)
                break
        if not accepted:
            layout.restore(saved)
    return len(layout.outputs)-count

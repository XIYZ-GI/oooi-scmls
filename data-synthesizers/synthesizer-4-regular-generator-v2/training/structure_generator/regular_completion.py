"""在原随机骨架上交替补供电与输出，保留全部已声明目标及时序。"""

from .config import FACING, MATERIALS, SIDES
from .density import fill
from .geometry import add
from .power import sockets
from .regular_policy import prioritize
from .front_output import allowed as output_allowed


def complete(search, rounds=2):
    layout, rng = search.layout, search.rng
    initial = len(layout.outputs)
    for _ in range(rounds):
        before = len(layout.outputs)
        from .regular_front_infill import grow as fill_front
        fill_front(search)
        fill(search)
        candidates = []
        for index, operation in enumerate(layout.operations):
            for material in operation['added']:
                if layout.blocks.get(material, {}).get('kind') not in MATERIALS:
                    continue
                for direction in SIDES:
                    observer = add(material, direction)
                    if layout.free(observer):
                        candidates.append((index, observer, FACING[tuple(-v for v in direction)]))
        rng.shuffle(candidates)
        for index, observer, facing in candidates:
            if search.simulations >= search.options.get('simulation_budget', 48) or len(layout.outputs) >= 32:
                return len(layout.outputs)-initial
            if not layout.free(observer):
                continue
            saved = layout.checkpoint()
            if not layout.put(observer, 'observer', facing):
                continue
            options = [p for p, kinds in sockets(layout.blocks, [observer]).items()
                       if 'push' in kinds and layout.free(p) and output_allowed(layout, p)
                       and p[:2] not in {v['piston'][:2] for v in layout.outputs}
                       and not any(q[:2] == p[:2] and q[2] > p[2] for q in layout.blocks)]
            rng.shuffle(options)
            prioritize(options, layout)
            observed = layout.checkpoint()
            accepted = False
            for p in options:
                layout.restore(observed)
                if not layout.put(p, 'piston', 'positive_z'):
                    continue
                layout.outputs.append(dict(piston=p, tick=layout.operations[index]['tick']+4))
                if search.valid():
                    layout.operations[index]['added'].append(observer)
                    accepted = True
                    break
            if accepted:
                # 新供电可能同时留下多个有效输出空位，四格厚也必须继续补齐。
                fill(search)
            else:
                layout.restore(saved)
        from .regular_supply_infill import grow
        grow(search)
        from .regular_rewire import improve
        improve(search)
        if len(layout.outputs) == before:
            break
    return len(layout.outputs)-initial

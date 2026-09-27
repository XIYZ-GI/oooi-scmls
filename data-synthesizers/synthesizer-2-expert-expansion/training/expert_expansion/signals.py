"""将输出供电与本体搬运分开，支持后继分支激活已搬走的输出活塞。"""

from collections import defaultdict

from .modules import xyz
from .power_connections import CONDUCTORS, facing_vector
from .transport import DIRECTIONS


def output_power(blocks):
    world = {xyz(b['position']): b['block'] for b in blocks}
    receivers = {}
    for origin, spec in world.items():
        if spec['kind'] == 'redstone_block':
            charged, delay = origin, 4
        elif spec['kind'] == 'observer':
            charged = tuple(p+d for p,d in zip(origin, facing_vector(spec)))
            delay = 6
            if origin != (charged[0], charged[1], charged[2]+1):
                receivers[charged] = delay
            if world.get(charged, {}).get('kind') not in CONDUCTORS:
                continue
        else:
            continue
        for dx,dy,dz in DIRECTIONS:
            p = (charged[0]+dx, charged[1]+dy, charged[2]+dz)
            if dz != -1:
                receivers[p] = delay
    return receivers


def constrain_outputs(model, choose, clock, group_time, nodes, task):
    sources = defaultdict(list)
    target_positions = {(t['x'],t['y'],t['z']-2) for t in task['targets']}
    powers = [output_power(n['blocks']) for n in nodes]
    for i,n in enumerate(nodes):
        for p,delay in powers[i].items():
            if p in target_positions:
                sources[p].append((i,delay))
    supports = {}
    for i,n in enumerate(nodes):
        local = powers[i]
        moved = clock[xyz(n['anchor'])]
        for j in n['covered']:
            target = task['targets'][j]
            position = (target['x'],target['y'],target['z']-2)
            tick = group_time[target['order']-1]
            if position in local:
                model.add(tick == moved+local[position]).only_enforce_if(choose[i])
                continue
            if j not in supports:
                possible = []
                for source,delay in sources[position]:
                    supplied = model.new_bool_var(f's{j}_{source}')
                    model.add_implication(supplied, choose[source])
                    source_tick = clock[xyz(nodes[source]['anchor'])]
                    model.add(tick == source_tick+delay).only_enforce_if(supplied)
                    possible.append(supplied)
                supports[j] = model.new_bool_var(f'has_source{j}')
                model.add_bool_or(possible).only_enforce_if(supports[j])
            model.add(moved <= tick-6).only_enforce_if(choose[i])
            model.add_implication(choose[i],supports[j])

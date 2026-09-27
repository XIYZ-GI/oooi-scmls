"""从目标和接口枚举局部可放置方案，输出可选子集不读取专家配方。"""

from itertools import combinations, product

from ..serialization import digest
from .modules import AXES, instantiate, orient, xyz
from .transport import transport_valid
from .signals import output_power


def placements(task, modules, complete_outputs=False):
    grid = [(x, y, z) for x in range(task['width']) for y in range(task['height'])
            for z in range(-task['depth']-1, -1)]
    space = set(grid)
    target = {xyz(t): i for i, t in enumerate(task['targets'])}
    loads = {(t['x'], t['y'], t['z']+i) for t in task['targets'] for i in range(10)}
    variants, emitted = {}, set()
    for source in modules:
        if source.get('procedural'):
            continue
        for swap, sx, sy in product((False, True), (-1, 1), (-1, 1)):
            m = orient(source, swap, sx, sy)
            variants[digest([m['core'], m['outputs'], m.get('slots', m['outputs']), m['ports']])] = m
    for m in variants.values():
        power = output_power(m['core'])
        for anchor in grid:
            a = dict(zip(AXES, anchor))
            core = [tuple(b['position'][k]+a[k] for k in AXES) for b in m['core']]
            if any(p not in space or p in loads for p in core):
                continue
            slots = [p for p in (m['outputs'] if complete_outputs else m.get('slots', m['outputs']))
                     if (p['x']+a['x'], p['y']+a['y'], p['z']+a['z']+2) in target]
            if complete_outputs and len(slots) != len(m['outputs']):
                continue
            for n in range(0 if m['ports'] or not m['outputs'] else 1, min(12-len(core), len(slots))+1):
                if complete_outputs and n != len(slots):
                    continue
                for chosen in combinations(slots, n):
                    blocks, outputs, ports = instantiate(m, a, chosen)
                    occupied = {xyz(b['position']) for b in blocks}
                    if anchor not in occupied or any(p not in space or p in loads for p in occupied):
                        continue
                    if not transport_valid([dict(blocks=blocks, anchor=a, tick=0, parent=None,
                                                 driver=(anchor[0], anchor[1], anchor[2]-1))]):
                        continue
                    covered = [target[xyz(t)] for t in outputs]
                    if len({task['targets'][i]['order'] for i in covered
                            if (task['targets'][i]['x']-a['x'],task['targets'][i]['y']-a['y'],
                                task['targets'][i]['z']-2-a['z']) in power}) > 1:
                        continue
                    children = [dict(anchor={**p['position'], 'z': p['position']['z']+
                                             (-1 if p['kind']=='pull' else 2)},
                                     delay=8 if p['kind']=='pull' else 4, driver=p['position'], kind=p['kind'])
                                for p in ports]
                    if any(xyz(p['anchor']) not in space for p in children):
                        continue
                    key = digest([blocks, anchor, children])
                    if key in emitted:
                        continue
                    emitted.add(key)
                    yield dict(blocks=blocks, core_count=len(m['core']), anchor=a, covered=covered, children=children,
                               module=m['id'], key=key)

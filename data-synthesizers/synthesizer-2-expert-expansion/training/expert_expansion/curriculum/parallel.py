"""合成并行推驱中心单元：观察者强充能前方方块，同时激活多个活塞。

经典课程让外部活塞直接顶观察者，命中“活塞推侦测端”禁忌；这里在观察者
后方增加一层被推方块作为耦合，外部活塞只接触该方块，禁忌由准入统一复核。
"""

from itertools import combinations

from ...serialization import digest

AXES = ('x', 'y', 'z')


def block(x, y, z, kind, facing='positive_z'):
    return dict(position=dict(x=x, y=y, z=z), block=dict(kind=kind, facing=facing))


def hub_module(hubs, outputs, ports, material='slime_block'):
    """按给定中心生成单元；观察者侧旁放被推方块，外部活塞只接触该方块。"""
    core = [block(0, 0, 0, material)]
    for index, (x, y) in enumerate(hubs):
        core.append(block(x, y, 0, 'observer'))
        core.append(block(x, y, 1, material))
        if index and x - hubs[index-1][0] > 1:
            for gap in range(hubs[index-1][0]+1, x):
                core.append(block(gap, y, 1, material))
    module = dict(core=core,
                  outputs=[dict(x=x, y=y, z=1) for x, y in outputs],
                  ports=[dict(position=dict(x=x, y=y, z=z), kind=kind) for x, y, z, kind in ports],
                  input_kind=material)
    module['id'] = digest(module)[:20]
    module['sources'] = [dict(expert='synthetic_parallel_hub', node=0)]
    module['synthetic'] = 'parallel_hub'
    return module


def output_slots(hubs):
    """强充能方块周围可放活塞的位置，跳过中心自身与已有方块。"""
    occupied = {hubs[0]}
    occupied.update((x, y+1) for x, y in hubs)
    slots = set()
    for x, y in hubs:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1)):
            point = (x+dx, y+dy)
            if point not in occupied:
                slots.add(point)
    return sorted(slots)


def hub_variants():
    """覆盖单中心、双中心、不同材料与不同规模输出的并行推驱单元。"""
    modules, seen = [], set()
    for hubs in (((-1, 0),), ((-1, 0), (-3, 0)), ((-1, 0), (-4, 0))):
        slots = output_slots(hubs)
        for material in ('slime_block', 'honey_block'):
            for count in range(2, min(len(slots), 8)+1):
                for points in combinations(slots, count):
                    module = hub_module(hubs, points, [], material)
                    if len(module['core'])+len(points) > 12:
                        continue
                    if module['id'] in seen:
                        continue
                    seen.add(module['id'])
                    modules.append(module)
    return modules


def augmented_library(library):
    """把并行推驱单元并入专家单元库，供现有装配器直接使用。"""
    value = dict(library)
    existing = {digest([m['core'], m['outputs'], m.get('ports')]) for m in library['modules']}
    extra = []
    for module in hub_variants():
        key = digest([module['core'], module['outputs'], module.get('ports')])
        if key in existing:
            continue
        existing.add(key)
        extra.append(module)
    value['modules'] = [*library['modules'], *extra]
    value['synthetic_parallel_units'] = len(extra)
    value['note'] = library.get('note', '') + ' 追加合成的并行推驱中心单元；禁忌与运行准入不变。'
    return value

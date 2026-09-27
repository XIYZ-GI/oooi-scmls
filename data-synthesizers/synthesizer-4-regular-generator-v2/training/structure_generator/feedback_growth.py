"""在原随机布局上原子生长跨组电源和先工作后回收的活塞闭环。"""

from .config import FACING, MATERIALS, SIDES
from .geometry import add
from .power import sockets
from .front_output import allowed as output_allowed


KINDS = ('next_source', 'redstone_recall', 'half_engine')


def operation(layout, kind, anchor, charges, members, tick):
    layout.operations.append(dict(kind=kind, anchor=anchor, charges=list(charges),
                                  added=sorted(members), tick=tick))


def outputs(search, members, tick, limit):
    """先声明输出及完成刻，再整机验证，不从失败模拟反写需求。"""
    layout, rng = search.layout, search.rng
    candidates = [p for p, kinds in sockets(layout.blocks, members).items()
                  if 'push' in kinds and layout.free(p) and output_allowed(layout, p)
                  and p[:2] not in {o['piston'][:2] for o in layout.outputs}
                  and not any(q[:2] == p[:2] and q[2] > p[2] for q in layout.blocks)]
    rng.shuffle(candidates)
    if search.options.get('regular'):
        from .regular_policy import prioritize
        prioritize(candidates, layout, tick)
    count = min(limit, 32-len(layout.outputs), len(candidates))
    count = rng.randint(min(2, count), count) if count else 0
    selected = set()
    for p in candidates:
        if len(selected) >= count:
            break
        if p[:2] in {o['piston'][:2] for o in layout.outputs}:
            continue
        if layout.put(p, 'piston'):
            layout.outputs.append(dict(piston=p, tick=tick))
            selected.add(p)
    return selected


def redstone_branch(search, index, support, side, recall):
    layout, rng = search.layout, search.rng
    parent = layout.operations[index]
    driver = add(support, side)
    anchor = add(driver, (0, 0, 2))
    lateral = rng.choice(SIDES)
    source = add(add(driver, (0, 0, 1)), lateral)
    member_anchor = add(anchor, lateral)
    material = rng.choice(MATERIALS)
    before = set(layout.blocks)
    if not layout.put(driver, 'piston') or not layout.put(anchor, material):
        return False
    if not layout.put(source, 'redstone_block'):
        return False
    charges = [anchor]
    if recall:
        if not layout.put(member_anchor, 'sticky_piston', 'negative_z'):
            return False
        choices = [d for d in SIDES if d != lateral]
        rng.shuffle(choices)
        for direction in choices:
            observer = add(anchor, direction)
            if layout.put(observer, 'observer', FACING[tuple(-v for v in direction)]):
                break
        else:
            return False
        layout.links.append(dict(kind='pull', driver=member_anchor, entry=source,
                                 tick=parent['tick']+4, role='回收跨组红石电源'))
    else:
        if not layout.put(member_anchor, material):
            return False
        # 电源属于下一段，活塞移近它后获得电力，下一段移动时断电。
        choices = [d for d in SIDES if sum(a*b for a, b in zip(d, lateral)) == 0]
        rng.shuffle(choices)
        for direction in choices:
            charge = add(member_anchor, direction)
            observer = add(charge, (0, 0, -1))
            if layout.free(charge) and layout.free(observer):
                layout.put(charge, material)
                layout.put(observer, 'observer')
                charges.append(charge)
                break
        else:
            return False
    members = set(layout.blocks)-before-{driver}
    if recall:
        members.remove(source)
    tick = parent['tick']+4
    added_outputs = outputs(search, members, tick+4, 12-len(members))
    if not added_outputs:
        return False
    members |= added_outputs
    parent['added'].append(driver)
    layout.links.append(dict(kind='push', driver=driver, entry=anchor,
                             tick=parent['tick'], role='下一段红石块供电'))
    operation(layout, '红石块跨组供电支路', anchor, charges, members, tick)
    if recall:
        operation(layout, '回拉红石电源', source, [], {source}, tick+8)
    return True


def half_engine(search, index, support, side):
    layout, rng = search.layout, search.rng
    parent = layout.operations[index]
    source = add(support, side)
    driver = add(source, (0, 0, 2))
    anchor = add(driver, (0, 0, 1))
    normal = rng.choice(SIDES)
    rear = add(driver, normal)
    recall = add(anchor, normal)
    material = rng.choice(MATERIALS)
    observer = add(anchor, normal, -1)
    specs = ((source, 'observer', 'positive_z'), (driver, 'piston', 'positive_z'),
             (rear, material, 'positive_z'), (anchor, material, 'positive_z'),
             (recall, 'sticky_piston', 'negative_z'),
             (observer, 'observer', FACING[normal]))
    for p, kind, facing in specs:
        if not layout.put(p, kind, facing):
            return False
    members = {anchor, recall, observer}
    tick = parent['tick']+4
    added = outputs(search, members, tick+4, 12-len(members))
    if not added:
        return False
    parent['added'].append(source)
    layout.links.extend((dict(kind='push', driver=driver, entry=anchor,
                              tick=parent['tick'], role='静止活塞先推动前段'),
                         dict(kind='pull', driver=recall, entry=rear,
                              tick=tick, role='前段回收已工作的驱动活塞')))
    operation(layout, '半动机前段', anchor, [anchor], members | added, tick)
    operation(layout, '半动机驱动回收', rear, [], {rear, driver}, tick+8)
    return True


def grow(search, kinds=KINDS, attempts=60, maximum=2):
    """同时提交完整闭环；任一失败恢复方块、输出、连接及操作记录。"""
    unknown = set(kinds)-set(KINDS)
    if unknown:
        raise ValueError('未知的跨组构造机制：'+','.join(sorted(unknown)))
    accepted = []
    for _ in range(attempts):
        if len(accepted) >= maximum or search.simulations >= search.options.get('simulation_budget', 48):
            break
        candidates = [(i, p) for i, op in enumerate(search.layout.operations)
                      if 'tick' in op for p in op['added']
                      if search.layout.blocks.get(p, {}).get('kind') in MATERIALS]
        if not candidates:
            break
        saved = search.layout.checkpoint()
        index, support = search.rng.choice(candidates)
        side, kind = search.rng.choice(SIDES), search.rng.choice(tuple(kinds))
        search.edits += 1
        if search.depth > 4 and kind != 'half_engine' and search.rng.random() < .65:
            # 跨组电源需要独立受电接口；避开原供电中心给同一活塞重复供电。
            extension = add(support, search.rng.choice(SIDES))
            if not search.layout.put(extension, search.layout.blocks[support]['kind']):
                search.layout.restore(saved)
                continue
            search.layout.operations[index]['added'].append(extension)
            support = extension
        success = (half_engine(search, index, support, side) if kind == 'half_engine'
                   else redstone_branch(search, index, support, side, kind == 'redstone_recall'))
        if success and search.valid():
            accepted.append(kind)
        else:
            search.layout.restore(saved)
    return accepted

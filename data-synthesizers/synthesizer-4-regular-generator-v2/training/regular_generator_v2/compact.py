"""两片输出区域共用根部，连接组也承担输出，避免外围模块拼接留下大空区。"""

from .config import MATERIALS, VERSION


def build_compact(plan):
    blocks, targets, links, groups = {}, [], [], []
    center = plan.get('center_outputs', [2, 8, 2, 8])
    root_side = plan.get('root_side', 3)
    if len(center) != 4 or any(x not in ((0, 2) if i % 2 == 0 else (8, 10)) for i, x in enumerate(center)):
        raise ValueError('中央输出不在可供电接口上')
    if root_side not in (3, 7):
        raise ValueError('根部侧输出接口无效')

    def put(x, y, z, kind, facing='positive_z'):
        if (x, y, z) in blocks:
            raise ValueError('紧凑拉驱方块位置冲突')
        blocks[x, y, z] = dict(kind=kind, facing=facing)

    def output(x, y, z, order):
        put(x, y, z, 'piston')
        targets.append(dict(x=x, y=y, z=z+2, order=order))

    def pull(x, y, z, branch):
        put(x, y, z, 'sticky_piston', 'negative_z')
        links.append(dict(kind='pull', driver=(x, y, z), entry=(x, y, z-1), branch=branch))

    def record(before):
        count = len(set(blocks)-before)
        if count > 12:
            raise ValueError('紧凑运动组超过十二块')
        groups.append(dict(blocks=count))

    for side, sign in enumerate((-1, 1)):
        # 每个叶组两列双排实心，后移一个观察者后可增加交错边缘输出。
        for i in range(6):
            before = set(blocks)
            x, material = 2*i, MATERIALS[i % 2]
            for column in (x, x+1):
                put(column, sign*4, -3, material)
                if column == x:
                    put(column, sign*5, -3, 'observer', 'negative_y' if sign == 1 else 'positive_y')
                else:
                    put(column, sign*4, -4, 'observer')
                    output(column, sign*5, -3, 3)
                output(column, sign*4, -2, 3)
                output(column, sign*3, -3, 3)
            for y in (2, 3, 4):
                put(x, sign*y, -4, material)
            record(before)
        for i in range(2):
            before = set(blocks)
            start, material = i*6, MATERIALS[(i+1) % 2]
            for x in range(start, start+5):
                put(x, sign, -3, material)
            for x in range(start, start+5, 2):
                put(x, sign, -4, 'observer')
                pull(x, sign*2, -3, f'分支:{side}:{i}')
            output(center[side*2+i], sign, -2, 2)
            record(before)

    before = set(blocks)
    for x in range(4, 7):
        put(x, 0, -2, 'slime_block')
    for x in (4, 6):
        put(x, 0, -3, 'observer')
        for sign in (-1, 1):
            pull(x, sign, -2, f'根部:{sign}:{x}')
        output(x, 0, -1, 1)
    output(root_side, 0, -2, 1)
    record(before)
    # 材料整体互换保持所有相邻隔离关系，身份去重仍合并等价变体。
    if plan.get('material_phase', 0):
        for spec in blocks.values():
            spec['kind'] = dict(slime_block='honey_block', honey_block='slime_block').get(spec['kind'], spec['kind'])
    position = lambda p: dict(x=p[0], y=p[1]+5, z=p[2]-1)
    targets = [{**position((t['x'], t['y'], t['z'])), 'order': t['order']} for t in targets]
    return dict(source=VERSION, family=plan['profile'],
                plan={**plan, 'regions': [dict(x=0, y=y, width=12, height=2) for y in (1, 8)],
                      'expected_targets': [dict(t) for t in targets]},
                task=dict(width=12, height=11, depth=4, targets=targets, rounds=3, load_blocks=10, max_ticks=96),
                proposal=dict(push=position((5, 0, -2)), blocks=[
                    dict(position=position(p), block=spec) for p, spec in sorted(blocks.items())]),
                construction=dict(groups=groups, operations=[], links=[
                    {**edge, 'driver': position(edge['driver']), 'entry': position(edge['entry'])} for edge in links]))

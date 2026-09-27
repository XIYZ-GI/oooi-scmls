"""多实心区、条带、折线和散点的薄层拉驱树；全部目标时序先于模拟固定。"""

from .config import LIMITS, LOAD_BLOCKS, MATERIALS, ROUNDS, VERSION


def build_composite(plan):
    width = plan['rectangle_width']
    branches = plan['branches']
    if branches not in (2, 4) or not 12 <= width <= 14:
        raise ValueError('复合构造要求二或四分支、矩形宽十二至十四格')
    blocks, targets, links, regions, groups = {}, [], [], [], []

    def put(x, y, z, kind, facing='positive_z'):
        if (x, y, z) in blocks:
            raise ValueError('复合构造方块重叠')
        blocks[x, y, z] = dict(kind=kind, facing=facing)

    def group(before):
        size = len(set(blocks)-before)
        if size > 12:
            raise ValueError('复合运动组超过十二块')
        groups.append(dict(blocks=size))

    def link(driver, entry, branch):
        links.append(dict(kind='pull', driver=driver, entry=entry, branch=branch))

    signs = (-1, 1) if branches == 4 else (1,)
    roots = []
    for sign in signs:
        # 每对子树上下镜像，材料交替；中心树只需要一台外部推动装置。
        xx = lambda x: sign*(x+3)
        for side in (0, 1):
            yy = lambda y: y+3 if side == 0 else -4-y
            branch = f'{sign}:{side}'
            region_points = [(xx(x), yy(y)) for x in range(width) for y in (0, 1)]
            regions.append(dict(x=min(p[0] for p in region_points),
                                y=min(p[1] for p in region_points), width=width, height=2))
            variant = (plan.get('tail_variant', 0)+side) % 2
            tail = [(0,), (0,), (0,), (0, 1) if variant == 0 else (1,), (), (3,)]
            for x in range(width+len(tail)):
                before = set(blocks)
                material = MATERIALS[(x+side+plan.get('material_phase', 0)) % 2]
                charge_y = -3 if x % 2 == 0 else -1
                outputs = (0, 1) if x < width else tail[x-width]
                # 输出用观察者直接供电，避免相邻未搬运列提前通电。
                if outputs:
                    for y in range(max(outputs)+1):
                        put(xx(x), yy(y), -4, material)
                for y in outputs:
                    put(xx(x), yy(y), -3, 'observer')
                    put(xx(x), yy(y), -2, 'piston')
                    targets.append(dict(x=xx(x), y=yy(y), z=0, order=x+1))
                for y in (-1, -2, -3):
                    put(xx(x), yy(y), -4, material)
                put(xx(x), yy(charge_y), -3, material)
                put(xx(x), yy(charge_y), -2, 'observer', 'negative_z')
                if x < width+len(tail)-1:
                    driver = (xx(x+1), yy(charge_y), -3)
                    put(*driver, 'sticky_piston', 'negative_z')
                    link(driver, (xx(x+1), yy(charge_y), -4), branch)
                group(before)
        before = set(blocks)
        for y in range(-3, 3):
            put(xx(-2), y, -3, 'slime_block')
        for y, side in ((2, 0), (-3, 1)):
            put(xx(-1), y, -3, 'slime_block')
            put(xx(-1), y, -2, 'observer', 'negative_z')
            driver = (xx(0), y, -3)
            put(*driver, 'sticky_piston', 'negative_z')
            link(driver, (xx(0), y, -4), f'{sign}:{side}')
        roots.append((xx(-2), 0, -3))
        group(before)

    push = roots[0]
    if branches == 4:
        before = set(blocks)
        for y in range(5):
            put(0, y, -2, 'slime_block')
        put(0, 0, -1, 'observer', 'negative_z')
        for entry in roots:
            driver = (entry[0], entry[1], entry[2]+1)
            put(*driver, 'sticky_piston', 'negative_z')
            link(driver, entry, f'根部:{entry[0]}')
        # 外部活塞避开子树黏性材料的邻接面，防止回拉时夹带外部装置。
        push = (0, 4, -2)
        group(before)

    ox, oy = (min(p[i] for p in blocks) for i in (0, 1))
    oz = max(p[2] for p in blocks)+2
    def position(p):
        return dict(x=p[0]-ox, y=p[1]-oy, z=p[2]-oz)
    orders = {o: i+1 for i, o in enumerate(sorted({t['order'] for t in targets}))}
    targets = [{**position((t['x'], t['y'], t['z'])), 'order': orders[t['order']]} for t in targets]
    for edge in links:
        edge.update(driver=position(edge['driver']), entry=position(edge['entry']))
    for region in regions:
        region.update(x=region['x']-ox, y=region['y']-oy)
    task = dict(width=max(p[0] for p in blocks)-ox+1, height=max(p[1] for p in blocks)-oy+1,
                depth=max(p[2] for p in blocks)-min(p[2] for p in blocks)+1,
                targets=targets, rounds=ROUNDS, load_blocks=LOAD_BLOCKS, max_ticks=192)
    if any(task[k] > LIMITS[k] for k in ('width', 'height', 'depth')) or len(targets) > LIMITS['targets']:
        raise ValueError('复合结构超过资源上限')
    return dict(source=VERSION, family=plan['profile'],
                plan={**plan, 'regions': regions, 'expected_targets': [dict(t) for t in targets]},
                task=task, proposal=dict(push=position(push), blocks=[
                    dict(position=position(p), block=b) for p, b in sorted(blocks.items())]),
                construction=dict(links=links, operations=[], groups=groups))

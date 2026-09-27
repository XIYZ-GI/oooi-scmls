"""参数化四向扇出原型：改变截面和回拉层级，目标在模拟前固定。"""

from .config import MATERIALS


def build_fan(width=5, height=5, delays=0, corners=12):
    if width not in (5, 6, 7) or height not in (5, 6, 7):
        raise ValueError('扇出原型当前支持五至七格的截面边长')
    if not 0 <= delays <= 15 or not 0 <= corners <= 15:
        raise ValueError('分支配置必须为四位掩码')
    blocks, targets, links, used = {}, [], [], set()

    def put(p, kind, facing='positive_z'):
        if p in blocks:
            raise ValueError('扇出构造位置冲突')
        blocks[p] = dict(kind=kind, facing=facing)

    def output(p, order):
        # 相邻供电中心共享目标边界，每列在构造时只分配给第一个中心。
        if p[:2] in used:
            return
        put(p, 'piston')
        targets.append(dict(x=p[0], y=p[1], z=p[2]+2, order=order))
        used.add(p[:2])

    def pull(p):
        put(p, 'sticky_piston', 'negative_z')
        links.append(dict(kind='pull', driver=p, entry=(*p[:2], p[2]-1)))

    put((2, 2, 0), 'slime_block')
    put((2, 2, 1), 'observer', 'negative_z')
    put((2, 2, 2), 'observer')
    output((2, 2, 3), 1)
    put((2, 2, -1), 'light_blue_glazed_terracotta')
    branches = [(1, 2, 1, 1), (2, 1, width-2, 1),
                (3, 2, width-2, height-2), (2, 3, 1, height-2)]
    for index, (ex, ey, cx, cy) in enumerate(branches):
        pull((ex, ey, 0))
        material = MATERIALS[(index+1) % 2]
        delayed = bool(delays >> index & 1)
        z = -1
        if delayed:
            # 入口组先回拉并供电，输出组再回拉；新增八刻来自真实搬运。
            put((ex, ey, -1), material)
            put((ex, ey, -2), 'observer')
            dx = 0 if ex == cx else (1 if cx > ex else -1)
            dy = 0 if dx else (1 if cy > ey else -1)
            ex, ey = ex+dx, ey+dy
            pull((ex, ey, -1))
            material, z = MATERIALS[index % 2], -2
        path = [(x, ey, z) for x in range(min(ex, cx), max(ex, cx)+1)]
        path += [(cx, y, z) for y in range(min(ey, cy), max(ey, cy)+1)]
        path += [(cx, cy, level) for level in range(z+1, 1)]+[(cx, cy, 2)]
        for position in dict.fromkeys(path):
            put(position, material)
        put((cx, cy, 1), 'observer')
        options = [(cx, cy, 3), (cx-1, cy, 2), (cx+1, cy, 2),
                   (cx, cy-1, 2), (cx, cy+1, 2)]
        if corners >> index & 1:
            y = 0 if index < 2 else height-1
            options = [p for p in options if p[:2] != (cx, y)]
            put((cx, y, 2), material)
            put((cx, y, 1), 'observer')
            options += [(cx, y, 3), (0 if index in (0, 3) else width-1, y, 2)]
        for position in options:
            output(position, 3 if delayed else 2)

    position = lambda p: dict(x=p[0], y=p[1], z=p[2]-5)
    ranks = {order: i+1 for i, order in enumerate(sorted({t['order'] for t in targets}))}
    targets = [{**position((t['x'], t['y'], t['z'])), 'order': ranks[t['order']]} for t in targets]
    return dict(source='regular-fan-prototype-v1', family='扇出拉驱阶段原型',
                plan=dict(mode='fan_pull', width=width, height=height, delays=delays,
                          corners=corners, expected_targets=[dict(t) for t in targets]),
                task=dict(width=width, height=height, depth=6 if delays else 5,
                          targets=targets, rounds=3, load_blocks=10, max_ticks=64),
                proposal=dict(push=position((2, 2, -1)), blocks=[
                    dict(position=position(p), block=v) for p, v in blocks.items()]),
                construction=dict(links=[{**e, 'driver': position(e['driver']),
                                         'entry': position(e['entry'])} for e in links], operations=[]))

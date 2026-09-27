"""由有向供电中心路径构造两格拉驱；整体验证负责判断机械干涉。"""

from ..templates import block
from ..serialization import digest


def pull_path(hubs, sides, output_choices=None):
    blocks = {}

    def put(x, y, z, kind, facing='positive_z'):
        key = (x, y, z)
        value = block(x, y, z, kind)
        value['block']['facing'] = facing
        if key in blocks and blocks[key] != value:
            raise ValueError('构造部件占位冲突')
        blocks[key] = value

    # 每级由前一级的反向粘性活塞回拉；相邻后层连接材料交替。
    for i, (x, y) in enumerate(hubs):
        material = 'slime_block' if i % 2 == 0 else 'honey_block'
        put(x, y, -3, 'observer')
        put(x, y, -2, material)
    for i, ((x, y), (nx, ny), side) in enumerate(zip(hubs, hubs[1:], sides)):
        dx, dy = nx-x, ny-y
        if (dx and dy) or abs(dx+dy) < 2:
            raise ValueError('相邻供电中心必须沿同一轴相隔至少两格')
        px, py = (0, side) if dx else (side, 0)
        material = 'honey_block' if i % 2 == 0 else 'slime_block'
        put(x+px, y+py, -2, 'sticky_piston', 'negative_z')
        distance = abs(dx+dy)
        for j in range(distance+1):
            put(x+px+(dx//distance)*j, y+py+(dy//distance)*j, -3, material)
    x, y = hubs[0]
    dx, dy = hubs[1][0]-x, hubs[1][1]-y
    px, py = (0, -sides[0]) if dx else (-sides[0], 0)
    put(x+px, y+py, -3, 'slime_block')
    push = dict(x=x+px, y=y+py, z=-3)
    adjacent = {}
    for i, (x, y) in enumerate(hubs):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            adjacent.setdefault((x+dx, y+dy), []).append(i+1)
    options = [(x, y, orders[0]) for (x, y), orders in adjacent.items()
               if len(orders) == 1 and (x, y, -2) not in blocks]
    chosen = options if output_choices is None else [options[i] for i in output_choices]
    for x, y, _ in chosen:
        put(x, y, -2, 'piston')
    if {t[2] for t in chosen} != set(range(1, len(hubs)+1)):
        raise ValueError('每个时序组至少一个输出')
    points = [b['position'] for b in blocks.values()]
    minx, miny = min(p['x'] for p in points), min(p['y'] for p in points)
    width, height = max(p['x'] for p in points)-minx+1, max(p['y'] for p in points)-miny+1
    for p in [*points, push]:
        p['x'] -= minx
        p['y'] -= miny
    targets = sorted([dict(x=x-minx, y=y-miny, z=0, order=order) for x, y, order in chosen], key=lambda t: (t['x'], t['y']))
    task = dict(width=width, height=height, depth=2, targets=targets, max_ticks=48, rounds=3, load_blocks=10)
    return {'task': task, 'proposal': {'blocks': list(blocks.values()), 'push': push},
            'family': 'path_pull', 'source': 'alternating_pull_path_v1',
            'topology': {'hubs': hubs, 'sides': sides}, 'group': digest([hubs, sides]), 'split': 'train'}

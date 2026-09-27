"""同刻多中心强充能分组，通过组间反向粘性活塞依次回拉。"""

from ..serialization import digest
from ..templates import block


def clustered_line(sizes, selected=None):
    blocks, centers, options = {}, [], {}

    def put(x, y, z, kind, facing='positive_z'):
        value = block(x, y, z, kind)
        value['block']['facing'] = facing
        key = x, y, z
        if key in blocks and blocks[key] != value:
            raise ValueError('分组连接部件占位冲突')
        blocks[key] = value

    offset = 0
    for order, count in enumerate(sizes, 1):
        material = 'slime_block' if order % 2 else 'honey_block'
        group = [1+2*(offset+i) for i in range(count)]
        for x in group:
            put(x, 1, -3, 'observer')
            put(x, 1, -2, material)
            centers.append((x, order))
        for x in group[:-1]:
            put(x+1, 1, -3, material)
        if order > 1:
            put(group[0]-1, 1, -3, material)
        if order < len(sizes):
            put(group[-1]+1, 1, -2, 'sticky_piston', 'negative_z')
        offset += count
    for x, order in centers:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = x+dx, 1+dy
            if (*point, -2) not in blocks:
                options.setdefault(point, set()).add(order)
    options = sorted((x, y, next(iter(orders))) for (x, y), orders in options.items() if len(orders) == 1)
    chosen = options if selected is None else [options[i] for i in selected]
    if {order for _, _, order in chosen} != set(range(1, len(sizes)+1)):
        raise ValueError('每组至少保留一个目标')
    for x, y, _ in chosen:
        put(x, y, -2, 'piston')
    task = {'width': 2*sum(sizes)+1, 'height': 3, 'depth': 2,
            'targets': [dict(x=x, y=y, z=0, order=order) for x, y, order in chosen],
            'max_ticks': 48, 'rounds': 3, 'load_blocks': 10}
    return {'task': task, 'proposal': {'blocks': list(blocks.values()),
            'push': dict(x=2 if sizes[0] > 1 else 1, y=1, z=-3)},
            'family': 'clustered_pull', 'group': 'clustered-'+digest(sizes),
            'source': 'parallel_centers_pull_groups_v1', 'usage': 'fit', 'split': 'train',
            'topology': {'group_center_counts': list(sizes)}}

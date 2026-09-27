"""十二列双排同步输出的三级回拉树，二十四个目标按同刻预设。"""

from .config import MATERIALS


def build_synchronous():
    blocks, targets, links, groups = {}, [], [], []

    def put(x, y, z, kind, facing='positive_z'):
        if (x, y, z) in blocks:
            raise ValueError('同步拉驱构造位置冲突')
        blocks[x, y, z] = dict(kind=kind, facing=facing)

    def record(before):
        size = len(set(blocks)-before)
        if size > 12:
            raise ValueError('同步拉驱运动组超十二块')
        groups.append(dict(blocks=size))

    def pull(x, y, z):
        put(x, y, z, 'sticky_piston', 'negative_z')
        links.append(dict(kind='pull', driver=(x, y, z), entry=(x, y, z-1), branch='同步区'))

    for i in range(6):
        before = set(blocks)
        x, material = i*2, MATERIALS[i % 2]
        for column in (x, x+1):
            put(column, 0, -3, material)
            put(column, -1, -3, 'observer', 'positive_y')
            for y, z in ((0, -2), (1, -3)):
                put(column, y, z, 'piston')
                targets.append(dict(x=column, y=y, z=z+2, order=1))
        # 连杆绕开观察者检测面，避免子根回拉前提前触发输出。
        for y in (0, -1, -2, -3):
            put(x, y, -4, material)
        record(before)
    for i in range(2):
        before = set(blocks)
        start, material = i*6, MATERIALS[(i+1) % 2]
        for x in range(start, start+5):
            put(x, -4, -3, material)
        for x in range(start, start+5, 2):
            put(x, -4, -4, 'observer')
            pull(x, -3, -3)
        record(before)
    before = set(blocks)
    for x in range(4, 7):
        put(x, -5, -2, 'slime_block')
    for x in (4, 6):
        put(x, -5, -3, 'observer')
        pull(x, -4, -2)
    record(before)
    position = lambda p: dict(x=p[0], y=p[1]+5, z=p[2])
    return dict(task=dict(width=12, height=7, depth=3, rounds=3, load_blocks=10, max_ticks=96,
                          targets=[{**position((t['x'], t['y'], t['z'])), 'order': 1} for t in targets]),
                proposal=dict(push=position((5, -5, -2)), blocks=[
                    dict(position=position(p), block=b) for p, b in sorted(blocks.items())]),
                construction=dict(groups=groups, operations=[], links=[
                    {**edge, 'driver': position(edge['driver']), 'entry': position(edge['entry'])}
                    for edge in links]))

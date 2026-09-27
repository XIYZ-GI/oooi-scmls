"""单入口组合大面积同推矩形、多时序矩形、条带、折线与散点。"""

from .composite import build_composite
from .config import LIMITS, VERSION
from .synchronous import build_synchronous


def build_hybrid(plan):
    chain = build_composite({**plan, 'mode': 'pull_composite', 'branches': 2})
    synchronous = build_synchronous()
    blocks, targets, links, groups, regions = {}, [], [], [], []

    def put(position, spec):
        key = tuple(position[a] for a in ('x', 'y', 'z'))
        if key in blocks:
            raise ValueError('混合拉驱树位置冲突')
        blocks[key] = dict(spec)

    for source, dx, turn in ((chain, -1, 2), (synchronous, 1, 3)):
        anchor = source['proposal']['push']
        def transform(p):
            x, y = p['x']-anchor['x'], p['y']-anchor['y']
            x, y = (-x, -y) if turn == 2 else (y, -x)
            return dict(x=x+dx, y=y, z=p['z']-anchor['z']-3)
        rotations = dict(positive_x='positive_y', positive_y='negative_x',
                         negative_x='negative_y', negative_y='positive_x')
        for item in source['proposal']['blocks']:
            spec = dict(item['block'])
            for _ in range(turn):
                spec['facing'] = rotations.get(spec['facing'], spec['facing'])
            put(transform(item['position']), spec)
        first_column = min(t['x'] for t in source['task']['targets'])
        for target in source['task']['targets']:
            # 根部额外八刻是两分支共有延迟；先按构造路径确定相对时序。
            tick = 16+8*(target['x']-first_column) if source is chain else 24
            targets.append({**transform(target), 'planned_tick': tick})
        for edge in source['construction']['links']:
            links.append({**edge, 'driver': transform(edge['driver']), 'entry': transform(edge['entry'])})
        groups.extend(source['construction']['groups'])
        local_regions = (chain['plan']['regions'] if source is chain else
                         [dict(x=0, y=5, width=12, height=2)])
        for region in local_regions:
            corners = [transform(dict(x=x, y=y, z=0))
                       for x in (region['x'], region['x']+region['width']-1)
                       for y in (region['y'], region['y']+region['height']-1)]
            regions.append(dict(x=min(p['x'] for p in corners), y=min(p['y'] for p in corners),
                                width=max(p['x'] for p in corners)-min(p['x'] for p in corners)+1,
                                height=max(p['y'] for p in corners)-min(p['y'] for p in corners)+1))
        links.append(dict(kind='pull', driver=dict(x=dx, y=0, z=-2),
                          entry=dict(x=dx, y=0, z=-3), branch='混合根部'))
    # 十块根组：侧伸输入避免外部推动器被子树材料夹带。
    for y in range(7):
        put(dict(x=0, y=y, z=-2), dict(kind='slime_block', facing='positive_z'))
    put(dict(x=0, y=0, z=-1), dict(kind='observer', facing='negative_z'))
    for x in (-1, 1):
        put(dict(x=x, y=0, z=-2), dict(kind='sticky_piston', facing='negative_z'))
    groups.append(dict(blocks=10))
    ox, oy = (min(p[i] for p in blocks) for i in (0, 1))
    oz = max(p[2] for p in blocks)+2
    def position(p):
        return dict(x=p['x']-ox, y=p['y']-oy, z=p['z']-oz)
    ranks = {tick: i+1 for i, tick in enumerate(sorted({t['planned_tick'] for t in targets}))}
    targets = [{**position(t), 'order': ranks[t['planned_tick']]} for t in targets]
    for edge in links:
        edge.update(driver=position(edge['driver']), entry=position(edge['entry']))
    for region in regions:
        region.update(x=region['x']-ox, y=region['y']-oy)
    task = dict(width=max(p[0] for p in blocks)-ox+1, height=max(p[1] for p in blocks)-oy+1,
                depth=max(p[2] for p in blocks)-min(p[2] for p in blocks)+1,
                targets=targets, rounds=3, load_blocks=10, max_ticks=192)
    if any(task[k] > LIMITS[k] for k in ('width', 'height', 'depth')) or len(targets) > LIMITS['targets']:
        raise ValueError('混合拉驱树超过资源上限')
    return dict(source=VERSION, family=plan['profile'], task=task,
                plan={**plan, 'branches': 3, 'regions': regions,
                      'expected_targets': [dict(t) for t in targets]},
                proposal=dict(push=position(dict(x=0, y=6, z=-2)), blocks=[
                    dict(position=position(dict(zip(('x', 'y', 'z'), p))), block=b)
                    for p, b in sorted(blocks.items())]),
                construction=dict(links=links, operations=[], groups=groups))

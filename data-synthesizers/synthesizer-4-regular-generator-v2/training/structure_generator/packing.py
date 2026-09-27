"""将全局布局转换为固定目标与时序的模拟请求。"""

from .config import LIMITS, VERSION
from .geometry import add, point, position


def pack(layout, category, depth, rounds=3, steps=0):
    offset = (min(p[0] for p in layout.blocks), min(p[1] for p in layout.blocks),
              max(p[2] for p in layout.blocks)+2)
    shift = lambda p: position(add(p, offset, -1))
    ranks = {t: i+1 for i, t in enumerate(sorted({v['tick'] for v in layout.outputs}))}
    targets = [{**shift(add(v['piston'], (0, 0, 2))), 'order': ranks[v['tick']]}
               for v in layout.outputs]
    blocks = [dict(position=shift(p), block=dict(b)) for p, b in sorted(layout.blocks.items())]
    width = max(b['position']['x'] for b in blocks)+1
    height = max(b['position']['y'] for b in blocks)+1
    if width > LIMITS['width'] or height > LIMITS['height'] or width*height*depth > LIMITS['volume']:
        return None
    task = dict(width=width, height=height, depth=depth, targets=sorted(targets, key=point),
                max_ticks=max(48, max((v['tick'] for v in layout.outputs), default=8)+12),
                rounds=rounds, load_blocks=10)
    links = [{**v, 'driver': shift(v['driver']), 'entry': shift(v['entry'])} for v in layout.links]
    operations = [{**v, 'anchor': shift(v['anchor']), 'charges': [shift(p) for p in v['charges']],
                   'added': [shift(p) for p in v['added']]} for v in layout.operations]
    for operation, original in zip(operations, layout.operations):
        if 'preferred_outputs' in original:
            operation['preferred_outputs'] = [shift(p) for p in original['preferred_outputs']]
        if 'preferred_pushes' in original:
            operation['preferred_pushes'] = [shift(p) for p in original['preferred_pushes']]
    return dict(task=task, proposal=dict(blocks=blocks, push=shift((0, 0, 0))),
                construction=dict(links=links, operations=operations, steps=steps),
                source=VERSION, family=category)

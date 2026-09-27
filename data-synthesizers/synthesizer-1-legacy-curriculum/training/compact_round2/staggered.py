"""前后交错目标的三格强充能课程，保留完整负载坐标。"""

from itertools import combinations
from ..templates import block
from .rules import geometry


def staggered_rules():
    for hubs in ((1,), (1, 3)):
        options = sorted({y for hub in hubs for y in (hub-1, hub, hub+1)})
        for count in range(2, len(options)+1):
            for points in combinations(options, count):
                blocks = [block(0, y, z, kind) for y in hubs
                          for z, kind in ((-4, 'observer'), (-3, 'slime_block'))]
                if len(hubs) == 2:
                    blocks.append(block(0, 2, -4, 'slime_block'))
                blocks += [block(0, y, -2 if y in hubs else -3, 'piston') for y in points]
                task = {'width': 1, 'height': max(options)+1, 'depth': 3,
                        'targets': [dict(x=0, y=y, z=0 if y in hubs else -1, order=1) for y in points],
                        'rounds': 3, 'max_ticks': 32, 'load_blocks': 10}
                yield {'task': task, 'proposal': {'blocks': blocks, 'push': dict(x=0, y=2 if len(hubs) == 2 else 1, z=-4)},
                       'family': 'strong_staggered', 'group': 'staggered-'+geometry(task),
                       'split': 'train', 'source': 'staggered_power_v1',
                       'scope': '由历史失败需求启发的交错目标课程；历史需求不再算未经查看的评估'}

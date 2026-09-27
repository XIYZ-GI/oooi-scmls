"""四格厚度的分层强充能供电与多目标输出课程。"""

from itertools import combinations
from ..templates import block
from ..serialization import digest
from .rules import geometry


def wide_rules():
    for hubs in ([(1, 1), (4, 1)], [(1, 1), (4, 1), (1, 4)]):
        if len(hubs) == 2:
            rear_slime = [(2, 1), (3, 1)]
            observers = [(2, 0, 'positive_y'), (3, 0, 'positive_y')]
        else:
            rear_slime = [(2, 1), (3, 1), (1, 2), (1, 3), (2, 2)]
            observers = [(2, 0, 'positive_y'), (3, 0, 'positive_y'), (0, 3, 'positive_x')]
        options = [(x+dx, y+dy) for x, y in hubs for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
        for count in range(6, min(len(options), 11)+1):
            # 各数量固定保留最多80个目标几何，不按模拟或模型表现挑选。
            choices = sorted(combinations(options, count), key=lambda p: digest(['wide_v1', p]))[:80]
            for points in choices:
                blocks = [block(x, y, -5, 'slime_block') for x, y in rear_slime]
                for x, y, facing in observers:
                    blocks.append(block(x, y, -5, 'observer'))
                    blocks[-1]['block']['facing'] = facing
                for x, y in hubs:
                    blocks += [block(x, y, -5, 'piston'), block(x, y, -3, 'observer'), block(x, y, -2, 'slime_block')]
                blocks += [block(x, y, -2, 'piston') for x, y in points]
                task = {'width': 6, 'height': 3 if len(hubs) == 2 else 6, 'depth': 4,
                        'targets': [dict(x=x, y=y, z=0, order=1) for x, y in points],
                        'max_ticks': 32, 'rounds': 3, 'load_blocks': 10}
                yield {'task': task, 'proposal': {'blocks': blocks, 'push': dict(x=2, y=1, z=-5)},
                       'family': 'strong_wide', 'group': 'wide-'+geometry(task), 'source': 'wide_power_v1',
                       'split': 'train', 'scope': '分层强充能规则的新目标组合'}

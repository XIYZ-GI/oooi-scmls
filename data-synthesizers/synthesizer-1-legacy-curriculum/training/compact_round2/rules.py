"""从完整机械骨架选择输出支路，来源身份保持不变。"""

from copy import deepcopy
from itertools import combinations

from ..compact.curriculum import record
from ..templates import block, geometry_key
from ..serialization import digest


def geometry(task):
    return digest(geometry_key([(t['x'], t['y'], t['z'], t['order']) for t in task['targets']]))


def mixed_rules(experts):
    experts = deepcopy(experts)
    # 第二组供电中心(3,2)可增加其右侧输出，形成八目标完整课程。
    extended = deepcopy(next(e for e in experts if e['name'] == '移动线15'))
    extended['reference']['targets'].append(dict(x=4, y=2, z=0, order=2))
    extended['request']['blocks'].append(block(4, 2, -2, 'piston'))
    experts.append(extended)
    for expert in experts:
        if expert['name'] not in ('移动线7', '移动线13', '移动线15'):
            continue
        assert expert['split'] == 'train'
        targets = [{k: t[k] for k in ('x', 'y', 'z', 'order')} for t in expert['reference']['targets']]
        outputs = {(t['x'], t['y'], t['z']-2): t for t in targets}
        blocks = expert['request']['blocks']
        for b in blocks:
            p = tuple(b['position'][a] for a in ('x', 'y', 'z'))
            if p in outputs and b['block'] != {'kind': 'piston', 'facing': 'positive_z'}:
                raise ValueError('目标输出不是独立正向普通活塞支路')
        groups = {t['order'] for t in targets}
        for count in range(len(groups), len(targets)+1):
            for chosen in combinations(targets, count):
                if {t['order'] for t in chosen} != groups:
                    continue
                wanted = {(t['x'], t['y'], t['z']-2) for t in chosen}
                # 保留全部观察者、连接带和回拉机构，仅按需求启用输出活塞支路。
                selected = [deepcopy(b) for b in blocks if
                            tuple(b['position'][a] for a in ('x', 'y', 'z')) not in outputs or
                            tuple(b['position'][a] for a in ('x', 'y', 'z')) in wanted]
                yield {'task': {'width': expert['width'], 'height': expert['height'], 'depth': expert['depth'],
                               'targets': deepcopy(list(chosen)), 'rounds': 3, 'max_ticks': 32, 'load_blocks': 10},
                       'proposal': {'blocks': selected, 'push': deepcopy(expert['request']['push_point'])},
                       'family': 'mixed_three' if len(groups) == 3 else 'mixed_two',
                       'group': 'expert-'+expert['group'], 'source': expert['id'], 'source_name': expert['name'],
                       'split': 'train', 'scope': '训练专家机械骨架的新输出组合，不是独立设计来源'}


def diagonal_strong():
    outputs = [(0, 1), (1, 0), (2, 1), (1, 2), (2, 3), (3, 2)]
    for count in range(2, 7):
        for chosen in combinations(outputs, count):
            blocks = [block(x, y, z, kind) for x, y in ((1, 1), (2, 2))
                      for z, kind in ((-3, 'observer'), (-2, 'slime_block'))]
            blocks.append(block(1, 2, -3, 'slime_block'))
            blocks += [block(x, y, -2, 'piston') for x, y in chosen]
            row = record(blocks, dict(x=1, y=2, z=-3),
                         [dict(x=x, y=y, z=0, order=1) for x, y in chosen], 'strong_compact')
            row['scope'] = '既有强充能原理的目标几何组合'
            yield row

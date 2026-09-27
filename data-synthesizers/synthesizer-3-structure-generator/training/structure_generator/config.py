"""生成预算、类别和空间约束。"""

from pathlib import Path

NAME = '移动线数据集结构生成器'
VERSION = 'layout-growth-v2'
OUTPUT = Path('data/generation/moving-line-generator-v2')
CATEGORIES = ('多目标同推', '推拉结合同推', '推拉结合多时序')
DEPTHS = (2, 3, 4)
LIMITS = dict(width=24, height=24, depth=4, volume=2304, targets=32)
AXES = ('x', 'y', 'z')
VECTORS = {'positive_x': (1, 0, 0), 'negative_x': (-1, 0, 0),
           'positive_y': (0, 1, 0), 'negative_y': (0, -1, 0),
           'positive_z': (0, 0, 1), 'negative_z': (0, 0, -1)}
FACING = {v: k for k, v in VECTORS.items()}
SIDES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))
MATERIALS = ('slime_block', 'honey_block')
CONDUCTORS = (*MATERIALS, 'iron_block', 'light_blue_glazed_terracotta')

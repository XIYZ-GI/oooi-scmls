"""规律密集结构的独立版本、物理协议与资源上限。"""

from pathlib import Path

VERSION = 'regular-solid-v2.3'
OUTPUT = Path('data/generation/regular-solid-v2')
SEED = 2026092407
HYBRID_PROFILE = '同推分时序混合拉驱'
COMPACT_PROFILE = '紧凑密集混合拉驱'
COMPOSITE_PROFILES = ('双区域拉驱复合', '四区域拉驱复合', HYBRID_PROFILE)
PROFILES = ('同时推实心', '分时序实心', '同时推与散点', '分时序与散点', *COMPOSITE_PROFILES, COMPACT_PROFILE)
COMPACT_LIMITS = dict(side=16, area=144, density=.5, empty_area=18, distance=3)
LIMITS = dict(width=64, height=64, depth=6, targets=256, blocks=1024)
MIN_AREA = 8
MIN_STRIP = 4
ROUNDS = 3
LOAD_BLOCKS = 10
MAX_TICKS = 96
MATERIALS = ('slime_block', 'honey_block')

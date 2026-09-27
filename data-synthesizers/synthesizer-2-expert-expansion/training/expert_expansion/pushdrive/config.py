"""推驱优化课程的预算、覆盖目标与空间上限。"""

import os
from pathlib import Path

OUTPUT = Path('data/generation/expert-expansion/curriculum-pushdrive-v1')
SEED = 2026092301
TOTAL_RECORDS = 20000
# 三类课程数量比例：多目标同推、推驱加拉驱同推、多时序四格推驱。
CATEGORIES = dict(同时推驱=8000, 推驱加拉驱=6000, 多时序推驱=6000)
LIMITS = dict(width=24, height=24, depth=10, volume=3072, targets=32)
WORKERS = max(1, min(8, (os.cpu_count() or 2)))
PENDING_PER_WORKER = 2
# 重复上限：同一目标几何、骨架与忽略时序布局分别限制。
EXACT_CAP = 2
GEOMETRY_CAP = 4
POSITION_CAP = 8
SKELETON_CAP = 256
MIN_TARGETS = 3


def size_band(width, height):
    area = width * height
    return '小截面' if area <= 25 else '中截面' if area <= 64 else '大截面'


def target_band(count):
    return '3至5目标' if count <= 5 else '6至12目标' if count <= 12 else '13至32目标'


def quota_table():
    """三维覆盖：尺寸带 × 目标数量带 × 类别，用于缺口采样。"""
    sizes = ('小截面', '中截面', '大截面')
    targets = ('3至5目标', '6至12目标', '13至32目标')
    cells = [(c, s, t) for c in CATEGORIES for s in sizes for t in targets]
    base, extra = divmod(TOTAL_RECORDS, len(cells))
    return {key: base + int(i < extra) for i, key in enumerate(cells)}

"""课程预算、覆盖条件和重复上限。"""

from ..config import ROOT, EXPANDED_RECORDS

OUTPUT = ROOT/'curriculum-balanced-v3'
SEED = 2026092217
CELLS = [(d, g) for d in range(2, 6) for g in range(1, 5)]
LIMITS = dict(width=24, height=24, depth=5, volume=512, targets=32)
TRAIN_COUNT = EXPANDED_RECORDS
HOLDOUT_PER_CELL = 32
EXACT_CAP = 2
GEOMETRY_CAP = 4
POSITION_CAP = 8
SKELETON_CAP = 512
PENDING_PER_WORKER = 2
SEARCH_STEPS = 400
OPTIONS_PER_NODE = 32


def quotas():
    base, extra = divmod(TRAIN_COUNT, len(CELLS))
    return {f'{d}:{g}': base+int(i < extra) for i, (d, g) in enumerate(CELLS)}


def size_band(width, height):
    area = width*height
    return '小截面' if area <= 25 else '中截面' if area <= 64 else '大截面'


def target_band(count):
    return '2至5目标' if count <= 5 else '6至12目标' if count <= 12 else '13至32目标'

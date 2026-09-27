"""组合完成后读取实际时序，输出完整准入证据。"""

import random

from ...evaluator import evaluate
from ...reinforcement.demands import geometry
from ...serialization import digest
from .assembly import assemble, variants
from .catalog import Catalog
from .config import size_band, target_band
from .repository import partition

_modules = None
_excluded = None


def initialize(library, excluded):
    global _modules, _excluded
    _modules = Catalog(variants(library))
    _excluded = excluded


def generate(job):
    index, seed, depth, groups, wanted_size, wanted_count = job
    rng = random.Random(f'{seed}:{index}')
    row, diagnostics = assemble(_modules, rng, depth, groups, wanted_size, wanted_count)
    result = dict(index=index, requested=dict(depth=depth, groups=groups,
                  size=wanted_size, targets=wanted_count), diagnostics=diagnostics)
    if row is None:
        return dict(**result, reason='回退装配未找到完整结构')
    task = row['task']
    # 同一机械结构只随机抽取一个空间条件，不展开四份厚度副本。
    actual_depth = task['depth']
    task['depth'] = depth
    task['max_ticks'] = max(64, 8*len(row['topology'])+24)
    row['actual_depth'] = actual_depth
    # 有限留白用于非贴边需求；同样受到全局目标重复上限约束。
    if rng.random() < .2:
        dx, dy, right, top = [rng.randrange(3) for _ in range(4)]
        width, height = task['width']+dx+right, task['height']+dy+top
        if max(width, height) <= 24 and width*height*depth <= 512:
            for p in [*[b['position'] for b in row['proposal']['blocks']],
                      row['proposal']['push'], *task['targets']]:
                p['x'] += dx
                p['y'] += dy
            task.update(width=width, height=height)
    # 位置与连接树不依赖实际时序，提前排除不会入库的候选。
    positions = geometry({**task, 'targets': [{**t, 'order': 1} for t in task['targets']]})
    if positions in _excluded:
        return dict(**result, reason='专家或保留需求排除')
    if partition(positions) != partition(row['group']):
        return dict(**result, reason='骨架及目标几何跨划分隔离')
    row['evaluation'] = evaluate(task, row['proposal'], foundation=True, require_activation=False,
                                 infer_timing=True, fail_fast=True)
    if not row['evaluation']['accepted']:
        return dict(**result, reason=row['evaluation']['reason'], failed=row)
    for target, order in zip(task['targets'], row['evaluation']['observed_order']):
        target['order'] = order
    row['id'] = digest([task, row['proposal']])[:24]
    measured_groups = len({t['order'] for t in task['targets']})
    if measured_groups not in (1, 2, 3, 4):
        return dict(**result, reason='实际时序组数超出1至4', failed=row)
    row['sampling_index'] = index
    row['coverage'] = dict(depth=depth, actual_depth=actual_depth, groups=measured_groups,
                           size=size_band(task['width'], task['height']),
                           targets=target_band(len(task['targets'])),
                           width=task['width'], height=task['height'], nodes=len(row['topology']))
    return dict(**result, reason='', row=row)

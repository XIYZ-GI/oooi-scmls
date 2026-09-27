"""单个推驱课程构造任务：构造、规范装配、真实模拟与类别判定。"""

import random
import time

from ...domain_rules import proposal_issues
from ...evaluator import evaluate
from ...serialization import digest
from ..composition import normalize
from .config import LIMITS, MIN_TARGETS, size_band, target_band
from .design import build


def pushed_targets(evaluation):
    """返回每轮真实完成的目标刻与真实拉驱块次数。"""
    cycles = evaluation.get('foundation', {}).get('cycles', [])
    pulled = sum(1 for cycle in cycles for block in cycle.get('blocks', []) if block.get('pulled'))
    return pulled


def generate(job):
    index, seed, category, band, wanted_size, wanted_targets = job
    rng = random.Random('%s:%s' % (seed, index))
    result = dict(index=index, requested=dict(category=category, band=band,
                                              size=wanted_size, targets=wanted_targets))
    built = build(rng, category, band)
    if not built:
        return dict(**result, reason='模板未能装配出完整结构')
    frame, push, meta = built
    frame.validate_targets()
    problems = frame.hub_issues()
    if problems:
        return dict(**result, reason='推驱中心静态核对失败：%s' % problems[0][0])
    if len(frame.targets) < MIN_TARGETS:
        return dict(**result, reason='目标列被后续层占用后不足三个')
    payload = frame.payload(push)
    if proposal_issues(dict(blocks=payload['blocks'], push=payload['push'])):
        return dict(**result, reason='结构违反活塞顶推侦测端等领域约束')
    row = normalize(payload['blocks'], payload['targets'], payload['push'], LIMITS)
    if row is None:
        return dict(**result, reason='结构超出空间资源上限')
    task = row['task']
    task['max_ticks'] = 64 + 12*meta['stages']
    evaluation = evaluate(task, row['proposal'], foundation=True, require_activation=False,
                          infer_timing=True, fail_fast=True)
    if not evaluation['accepted']:
        return dict(**result, reason=evaluation['reason'], failed=row)
    orders = evaluation['observed_order']
    groups = len(set(orders))
    pulled = pushed_targets(evaluation)
    targets = len(task['targets'])
    size = size_band(task['width'], task['height'])
    count_band = target_band(targets)
    if targets < MIN_TARGETS:
        return dict(**result, reason='目标数量少于三个', failed=row)
    if category == '同时推驱' and groups != 1:
        return dict(**result, reason='同一层目标没有同刻完成', failed=row)
    if category == '推驱加拉驱' and (groups != 1 or pulled == 0):
        return dict(**result, reason='拉驱结构没有真实回拉或目标不同刻', failed=row)
    if category == '多时序推驱' and groups < 2:
        return dict(**result, reason='多时序结构只出现一个时序组', failed=row)
    row['id'] = digest([task, row['proposal']])[:24]
    row['family'] = 'pushdrive_%s' % meta['category']
    row['group'] = digest([meta['category'], meta['stages'], meta['hooks'],
                           sorted((t['x'], t['y']) for t in task['targets'])])
    row['coverage'] = dict(category=category, band=band, size=size, targets_band=count_band,
                           targets=targets, groups=groups, depth=task['depth'],
                           actual_depth=task['depth'], pulled=pulled, stages=meta['stages'],
                           hooks=meta['hooks'], width=task['width'], height=task['height'],
                           blocks=len(row['proposal']['blocks']),
                           seconds=round(evaluation.get('seconds', 0.0), 3))
    row['evaluation'] = {k: evaluation[k] for k in
                         ('engine_version', 'load_blocks', 'simulated_ticks', 'observed_order')
                         if k in evaluation}
    row['requested_sampling'] = result['requested']
    return dict(**result, reason='', row=row)

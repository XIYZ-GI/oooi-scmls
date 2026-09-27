"""候选构造、固定需求的三轮验证与机制准入。"""

import random

from ..evaluator import evaluate
from ..serialization import digest
from .construction import construct
from .coverage import describe
from .extension_constraints import issue as extension_issue, counts as extension_counts
from .evidence import inspect
from .geometry import canonical, point


def generate(job):
    index, seed, category, depth, dense, *constraints = job
    min_targets, min_density = constraints[:2] or (3, 0.0)
    options = dict(constraints[2]) if len(constraints) > 2 else {}
    if options.get('extension_placement','any') != 'any' or options.get('min_saturated_extensions',0):
        options['min_extensions'] = max(options.get('min_extensions',0),
                                        options.get('min_saturated_extensions',0),1)
    if options.get('search'):
        options.setdefault('target_goal', min_targets)
        # 密度用于保守容量上界；最终准入仍使用真实截面重新检查。
        options.setdefault('density_goal', min_density)
    builder = construct
    if options.get('search'):
        from .search import construct as builder
    arguments = (random.Random(f'{seed}:{index}'), category, depth, dense)
    row, reason = builder(*arguments, options=options) if options.get('search') else builder(*arguments)
    result = dict(index=index, requested=dict(category=category, depth=depth, dense=dense,
                                             min_targets=min_targets, min_density=min_density, options=options))
    if row is None:
        return dict(**result, reason=reason)
    task = row['task']
    long_side, short_side = sorted((task['width'], task['height']), reverse=True)
    if long_side < options.get('min_long_side', 0) or short_side < options.get('min_short_side', 0):
        return dict(**result, reason='实际截面未达到本批尺寸下限')
    if len(task['targets']) < min_targets:
        return dict(**result, reason='目标数量未达到本批下限')
    if len(task['targets'])/(task['width']*task['height']) < min_density:
        return dict(**result, reason='目标密度未达到本批下限')
    if options.get('diverse_batch'):
        from .batch.mixed_validation import shape_issue
        reason = shape_issue(row, options['diverse_batch'])
        if reason:
            return dict(**result, reason=reason)
    elif options.get('regular'):
        from .regular_admission import inspect_shape
        row['shape'], reason = inspect_shape(row, options)
        if reason:
            return dict(**result, reason=reason)
    evaluation = evaluate(row['task'], row['proposal'], foundation=True,
                          require_activation=False, fail_fast=True, capture=True)
    if not evaluation['accepted']:
        return dict(**result, reason=evaluation['reason'])
    if options.get('diverse_batch') or options.get('regular') or depth > 4 or row.get('construction', {}).get('feedback_growth'):
        from ..evaluator import ROUND_GAP_TICKS
        evidence_row = {**row, 'task': {**task, 'max_ticks': task['max_ticks']+ROUND_GAP_TICKS}}
    else:
        evidence_row = row
    evidence, reason = inspect(evidence_row, evaluation)
    if evidence is None:
        return dict(**result, reason=reason)
    if options.get('diverse_batch'):
        from .batch.mixed_validation import physics
        physical, reason = physics(row, evidence)
        if reason:
            return dict(**result, reason=reason)
        row.update(physical)
    elif options.get('regular') or depth > 4 and category == '推拉结合多时序':
        from .regular_admission import inspect_physics
        physical, reason = inspect_physics(row, evidence)
        if reason:
            return dict(**result, reason=reason)
        row.update(physical)
    elif row.get('construction', {}).get('feedback_growth'):
        from .feedback_ablation import verify, verify_redstone
        controls, reason = verify({**row, 'mechanisms': evidence})
        if reason:
            return dict(**result, reason=reason)
        redstone, reason = verify_redstone(row)
        if reason:
            return dict(**result, reason=reason)
        row.update(pull_ablation=controls, redstone_ablation=redstone)
    reason = extension_issue(evidence,options)
    if reason:
        return dict(**result, reason=reason)
    evidence['extension_placements'] = extension_counts(evidence)
    groups = len({t['order'] for t in row['task']['targets']})
    if category == '多目标同推' and groups != 1:
        return dict(**result, reason='同推目标没有同时完成')
    if category != '多目标同推' and not evidence['functional_pulls']:
        return dict(**result, reason='没有影响输出的真实拉驱')
    if category == '推拉结合同推' and groups != 1:
        return dict(**result, reason='推拉结合后的目标未同时完成')
    if category == '推拉结合多时序' and groups < 2:
        return dict(**result, reason='没有多个目标时序')
    task = row['task']
    row['id'] = digest([task, row['proposal']])[:24]
    row['canonical'] = canonical(row['proposal']['blocks'], task['targets'])
    output_positions = {(t['x'], t['y'], t['z']-2) for t in task['targets']}
    row['skeleton'] = canonical([b for b in row['proposal']['blocks']
                                 if point(b['position']) not in output_positions])
    row['mechanisms'] = evidence
    row['evaluation'] = {k: v for k, v in evaluation.items() if k not in ('trace', 'foundation')}
    row['coverage'] = describe(row)
    row['requested_sampling'] = result['requested']
    row['generator'] = dict(seed=seed, index=index)
    return dict(**result, reason='', row=row)

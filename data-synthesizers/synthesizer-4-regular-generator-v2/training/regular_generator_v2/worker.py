"""规则构造、完整形态检查与真实十负载三轮模拟。"""

from ..domain_rules import proposal_issues
from ..evaluator import evaluate
from .admission import shape_issue
from .builders import build
from .identity import identities
from .patterns import structure_pattern
from .plans import sample_plan


def generate(job):
    index, seed, profile = job
    plan = sample_plan(seed, index, profile)
    result = dict(index=index, profile=profile, plan=plan)
    try:
        row = build(plan)
        metrics, reason = shape_issue(row)
    except ValueError as error:
        return dict(result, reason=str(error))
    if reason:
        return dict(result, reason=reason)
    if proposal_issues(row['proposal']):
        return dict(result, reason='构造违反领域禁忌')
    # 固定计划时序，严禁使用 infer_timing 修改答案标签，也不删除失败目标。
    composite = plan['mode'] in ('pull_composite', 'hybrid_pull', 'compact_pull')
    evaluation = evaluate(row['task'], row['proposal'], fail_fast=True, capture=composite)
    if not evaluation['accepted']:
        return dict(result, reason=evaluation['reason'])
    if composite:
        from .pull_validation import validate_pulls
        evidence, reason = validate_pulls(row, evaluation)
        if reason:
            return dict(result, reason=reason)
        row.update(evidence)
        evaluation.pop('trace', None)
    row.update(identities(row))
    row.update(shape=metrics, structure_pattern=structure_pattern(row['proposal']['blocks']),
               evaluation=evaluation, generator=dict(seed=seed, index=index))
    task = row['task']
    row['coverage'] = dict(width=task['width'], height=task['height'], actual_depth=task['depth'],
                           targets=len(task['targets']), groups=metrics['groups'],
                           blocks=len(row['proposal']['blocks']),
                           current_model_compatible=task['width']*task['height']*task['depth'] <= 512
                           and len(task['targets']) <= 32)
    return dict(result, reason='', row=row)

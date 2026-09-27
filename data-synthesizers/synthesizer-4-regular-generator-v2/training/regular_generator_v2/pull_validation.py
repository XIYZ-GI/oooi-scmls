"""真实回拉轨迹与保持几何位置的消融，防止把装饰粘性活塞当拉驱。"""

from copy import deepcopy

from ..evaluator import ROUND_GAP_TICKS, evaluate
from ..structure_generator.evidence import inspect


def validate_pulls(row, evaluation):
    # 轨迹的绝对周期含轮间间隔，不能用单轮观察刻数直接取模。
    evidence_row = {**row, 'task': {**row['task'], 'max_ticks': row['task']['max_ticks']+ROUND_GAP_TICKS}}
    mechanisms, reason = inspect(evidence_row, evaluation)
    if reason:
        return None, reason
    if mechanisms['functional_pulls'] != len(row['construction']['links']) or mechanisms['functional_pushes']:
        return None, '内部接力没有全部通过拉驱完成'
    # 全部链边已逐条核对三轮实际搬运及有效输出；消融另检查整树和最晚支路。
    links = mechanisms['links']
    latest = max(links, key=lambda edge: edge['end'])
    tests = [('全部回拉', links), ('末端回拉', [latest])]
    checks = []
    for name, selected in tests:
        proposal = deepcopy(row['proposal'])
        drivers = {tuple(v['driver'][a] for a in ('x', 'y', 'z')) for v in selected}
        for b in proposal['blocks']:
            if tuple(b['position'][a] for a in ('x', 'y', 'z')) in drivers:
                b['block']['kind'] = 'piston'
        control = evaluate({**row['task'], 'rounds': 1}, proposal, fail_fast=True)
        if control['accepted'] or control['reason'] != '时限内未完成全部目标的十块负载':
            return None, '取消回拉后未观察到预期的负载输出丢失'
        checks.append(dict(name=name, drivers=[v['driver'] for v in selected],
                           accepted=control['accepted'], reason=control['reason']))
    return dict(mechanisms=mechanisms, pull_ablation=checks), ''

"""通过保留几何位置的回拉消融，核对拉驱对负载输出的实际贡献。"""

from copy import deepcopy

from ..evaluator import evaluate
from .geometry import point


def verify_pulls(row):
    checks = []
    for link in row['mechanisms']['links']:
        if link['kind'] != 'pull':
            continue
        proposal = deepcopy(row['proposal'])
        for b in proposal['blocks']:
            if b['position'] == link['driver']:
                b['block']['kind'] = 'piston'
                break
        evaluation = evaluate({**row['task'], 'rounds': 1}, proposal, capture=True,
                              foundation=True, require_activation=False, fail_fast=False)
        trace = evaluation.get('trace', [])
        if not trace or trace[-1]['snapshot']['tick'] < row['task']['max_ticks']:
            return None, '取消回拉后的对照未完成完整观察周期'
        initial = {point(b['position']): b['id'] for b in trace[0]['snapshot']['blocks']}
        actual = {b['id']: point(b['position']) for b in trace[-1]['snapshot']['blocks']}
        lost = []
        for index, target in enumerate(row['task']['targets']):
            x, y, z = point(target)
            if not all(actual.get(initial[x, y, z+i]) == (x, y, z+i+1) for i in range(10)):
                lost.append(index)
        if not lost:
            return None, '取消回拉后全部目标仍可完成，不能作为有效拉驱展示'
        checks.append(dict(driver=link['driver'], lost_targets=lost,
                           lost_target_count=len(lost), reason=evaluation['reason']))
    return checks, ''

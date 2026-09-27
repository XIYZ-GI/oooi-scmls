"""通过连续三轮负载对照验证复位回拉，不能只看第一轮输出。"""

from copy import deepcopy

from ..evaluator import evaluate


def check(row, position, replacement, role):
    proposal = deepcopy(row['proposal'])
    matches = [b for b in proposal['blocks'] if b['position'] == position]
    if len(matches) != 1:
        return None, '消融对象没有唯一方块'
    matches[0]['block']['kind'] = replacement
    evaluation = evaluate(row['task'], proposal, foundation=True,
                          require_activation=False, fail_fast=True)
    reset_failed = any(not r['translation'] for r in evaluation['rounds'])
    if evaluation['accepted'] and not reset_failed:
        return None, '取消'+role+'后仍能连续三轮完成全部目标'
    if not evaluation['simulator_started'] or '三十秒' in evaluation['reason']:
        return None, '消融没有完成有效物理对照：'+evaluation['reason']
    return dict(driver=position, role=role, accepted=False,
                completed_rounds=len(evaluation['rounds']),
                failed_round=(next(r['round'] for r in evaluation['rounds'] if not r['translation'])
                              if reset_failed else len(evaluation['rounds'])+1),
                load_protocol_accepted=evaluation['accepted'],
                reset_failed=reset_failed,
                reason=evaluation['reason'] or '取消回收后本体不能逐轮完整前进一格'), ''


def verify(row):
    checks = []
    for link in row['mechanisms']['links']:
        if link['kind'] != 'pull':
            continue
        result, reason = check(row, link['driver'], 'piston', '回拉')
        if reason:
            return None, reason
        checks.append(result)
    return checks, ''


def verify_redstone(row):
    sources = {tuple(b['position'][a] for a in 'xyz'): b['position']
               for b in row['proposal']['blocks'] if b['block']['kind'] == 'redstone_block'}
    checks = []
    for position in sources.values():
        result, reason = check(row, position, 'glass', '红石块供电')
        if reason:
            return None, reason
        checks.append(result)
    return checks, ''

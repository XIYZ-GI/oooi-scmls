"""保持全部目标和推拉功能的单方块删除检查，用于展示前去除冗余。"""

from copy import deepcopy

from ..evaluator import evaluate
from ..serialization import digest
from .evidence import inspect
from .coverage import trim_bounds
from .extension_constraints import issue as extension_issue, counts as extension_counts
from .geometry import canonical, point


def reduce(row):
    row = deepcopy(row)
    evaluation = evaluate(row['task'], row['proposal'], foundation=True, require_activation=False,
                          fail_fast=True, capture=True)
    if not evaluation['accepted']:
        return None, evaluation['reason']
    evidence, reason = inspect(row, evaluation)
    if reason:
        return None, reason
    row['mechanisms'] = evidence
    original_id = row['id']
    reserved = {point(row['proposal']['push'])}
    for link in row['construction']['links']:
        reserved.update((point(link['driver']), point(link['entry'])))
    outputs = {(t['x'], t['y'], t['z']-2) for t in row['task']['targets']}
    reserved.update(outputs)
    removed, attempts = [], 0
    thinner = False
    for _ in range(2):
        changed = False
        candidates = sorted(row['proposal']['blocks'], key=lambda b: b['block']['kind'] != 'observer')
        for block in candidates:
            if point(block['position']) in reserved:
                continue
            proposal = {**row['proposal'], 'blocks': [b for b in row['proposal']['blocks'] if b != block]}
            attempts += 1
            evaluation = evaluate(row['task'], proposal, foundation=True, require_activation=False,
                                  fail_fast=True, capture=True)
            if not evaluation['accepted']:
                continue
            trial = {**row, 'proposal': proposal}
            evidence, reason = inspect(trial, evaluation)
            if reason:
                continue
            actual_depth = max(b['position']['z'] for b in proposal['blocks'])-min(
                b['position']['z'] for b in proposal['blocks'])+1
            if actual_depth != row['task']['depth']:
                thinner = True
                continue
            row['proposal'], row['mechanisms'] = proposal, evidence
            row['evaluation'] = {k: v for k, v in evaluation.items() if k not in ('trace', 'foundation')}
            removed.append(block)
            changed = True
        if not changed:
            break
    if thinner:
        return None, '存在保持功能但减少厚度的单方块删除，跳过该厚度代表例'
    trim_bounds(row)
    options = row.get('requested_sampling',{}).get('options',{})
    long_side,short_side = sorted((row['task']['width'],row['task']['height']),reverse=True)
    if long_side < options.get('min_long_side',0) or short_side < options.get('min_short_side',0):
        return None, '删除冗余后未达到请求的实际尺寸，跳过该尺寸代表例'
    reason = extension_issue(row['mechanisms'],options)
    if reason:
        return None, reason
    row['mechanisms']['extension_placements'] = extension_counts(row['mechanisms'])
    row['id'] = digest([row['task'], row['proposal']])[:24]
    row['canonical'] = canonical(row['proposal']['blocks'], row['task']['targets'])
    outputs = {(t['x'],t['y'],t['z']-2) for t in row['task']['targets']}
    row['skeleton'] = canonical([b for b in row['proposal']['blocks'] if point(b['position']) not in outputs])
    row['coverage']['blocks'] = len(row['proposal']['blocks'])
    row['reduction'] = dict(origin=original_id, attempts=attempts, removed=removed)
    return row, ''

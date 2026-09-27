"""整机三轮轨迹中的分层推拉证据及逐边回拉消融。"""

from ..evaluator import ROUND_GAP_TICKS
from .evidence import inspect
from .regular_admission import inspect_physics


def validate(row, evaluation):
    evidence_row = {**row, 'task': {**row['task'], 'max_ticks': row['task']['max_ticks']+ROUND_GAP_TICKS}}
    mechanisms, reason = inspect(evidence_row, evaluation)
    if reason:
        return None, reason
    physical, reason = inspect_physics(row, mechanisms)
    if reason:
        return None, reason
    return dict(mechanisms=mechanisms, **physical), ''

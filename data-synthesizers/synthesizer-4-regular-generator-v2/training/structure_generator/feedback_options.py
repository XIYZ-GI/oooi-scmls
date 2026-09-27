"""让原生成入口按种子索引混合普通生长与跨组供电闭环。"""

from .feedback_growth import KINDS


def options_for(index, mode='mixed', depth=4):
    if mode not in ('mixed', 'off', *KINDS):
        raise ValueError('未知的跨组供电构造模式')
    if mode == 'off' or mode == 'mixed' and index % 4 == 0:
        return {}
    kinds = KINDS if mode == 'mixed' else (mode,)
    return dict(feedback_growth=True, feedback_kinds=kinds,
                feedback_seed=depth == 4 and (mode != 'mixed' or index % 2 == 1),
                feedback_minimum=1, feedback_maximum=3,
                feedback_attempts=120, feedback_continuation=2)

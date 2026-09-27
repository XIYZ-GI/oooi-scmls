"""规律生长的两类实心区域配额与搜索预算，沿用原随机入口。"""

from ..regular_generator_v2.solid_regions import TIMING_MODES


def options_for(index, depth, mode='balanced'):
    from .layer_scheme import LAYERED_DEPTHS
    if depth not in LAYERED_DEPTHS:
        raise ValueError('规律分层支持四、五、六格厚度')
    if mode not in (*TIMING_MODES, 'balanced'):
        raise ValueError('未知的实心区域时序模式')
    selected = ('simultaneous', 'partitioned')[index % 2] if mode == 'balanced' else mode
    return dict(regular=True, mixed=True, layered=True, depth=depth, supply_trials=4,
                rectangular_seed=index % 3 == 0, layered_relay=index % 3 == 1,
                front_layers=depth-1, min_groups=4, min_simultaneous=11,
                simultaneous_scope='any', solid_timing=selected,
                min_solid_area=11, max_empty_area=4, completion_rounds=2,
                branch_attempts=60, edit_budget=2400 if depth == 4 else 4800)

"""原随机生成流程的实心、空洞和时序联合准入，物理失败不能修改目标补救。"""

from ..regular_generator_v2.compactness import describe_compactness
from ..regular_generator_v2.metrics import describe_targets
from ..regular_generator_v2.composite_admission import output_distances
from .verification import verify_pulls
from ..regular_generator_v2.rectangles import cells, rectangles
from ..regular_generator_v2.solid_regions import describe_regions, select_regions


def inspect_shape(row, options):
    compact = describe_compactness(row)
    shape = describe_targets(row['task']['targets'])
    shape['compactness'] = compact
    shape['max_simultaneous'] = max((v['targets'] for v in shape['same_time'].values()), default=0)
    independent, used = [], set()
    same_time_regions = [dict(r, order=group) for group in sorted({t['order'] for t in row['task']['targets']})
                         for r in rectangles({(t['x'], t['y']) for t in row['task']['targets'] if t['order'] == group})]
    same_time_regions.sort(key=lambda r: -r['area'])
    for rectangle in same_time_regions:
        covered = cells(rectangle)
        if not covered & used:
            independent.append(rectangle)
            used.update(covered)
    shape['independent_rectangles'] = independent
    shape['outside_selected_rectangles'] = len(row['task']['targets'])-len(used)
    solid_area = max((r['area'] for r in same_time_regions), default=0)
    shape['largest_simultaneous_rectangle_area'] = solid_area
    region_report = describe_regions(row['task']['targets'])
    selected = select_regions(region_report, options.get('solid_timing', 'either'),
                              max(11, options.get('min_simultaneous', 11)),
                              options.get('simultaneous_scope', 'any'))
    shape['solid_regions'] = region_report
    shape['selected_regions'] = selected
    shape['largest_partitioned_rectangle_area'] = region_report['largest_partitioned_area']
    shape['largest_qualifying_rectangle_area'] = selected['largest_area']
    group_count = (region_report['min_simultaneous'] if selected['scope'] == 'every'
                   else region_report['max_simultaneous'])
    checks = (
        (compact['target_density'] >= options.get('density_goal', .72), '完整截面目标密度不足'),
        (compact['largest_empty_area'] <= options.get('max_empty_area', 4), '连续无目标区域过大'),
        (compact['max_distance_to_target'] is not None and
         compact['max_distance_to_target'] <= options.get('max_target_distance', 1), '连接区域离目标过远'),
        (shape['groups'] >= options.get('min_groups', 4), '随机结构的时序组不足'),
        (group_count >= selected['minimum'], '随机结构的同推目标不足十一点'),
        (selected['largest_area'] >= max(options.get('min_solid_area', 8),
                           compact['area']*options.get('min_solid_fraction', .4)),
         '随机结构缺少满足时序类型与面积要求的实心区'),
        (len(selected['independent']) >= options.get('min_rectangles', 1 if compact['area'] <= 30 else 2),
         '随机结构的独立合格实心区域不足'),
    )
    return shape, next((reason for accepted, reason in checks if not accepted), '')


def inspect_physics(row, mechanisms, require_mixed=True):
    """核对推拉混合接力、逐列距离与每条回拉的真实贡献。"""
    front = None
    if row.get('construction', {}).get('layer_scheme') or row.get('construction', {}).get('output_policy'):
        from .front_output import inspect as inspect_front
        front, reason = inspect_front(row)
        if reason:
            return None, reason
    if (not mechanisms['functional_pulls'] or
            mechanisms['functional_pulls']+mechanisms['functional_pushes'] != len(row['construction']['links'])):
        return None, '内部推拉连接缺少完整有效运动证据'
    layers = None
    if require_mixed:
        from .layered_evidence import inspect_layers
        layers, reason = inspect_layers(row, mechanisms)
        if reason:
            return None, reason
    distances, reason = output_distances(row)
    if reason:
        return None, reason
    checks, reason = verify_pulls({**row, 'mechanisms': mechanisms})
    if reason:
        return None, reason
    redstone = []
    if row.get('construction', {}).get('feedback_growth'):
        from .feedback_ablation import verify_redstone
        redstone, reason = verify_redstone(row)
        if reason:
            return None, reason
    return dict(output_distances=distances, pull_ablation=checks, layer_evidence=layers,
                redstone_ablation=redstone, front_output=front), ''

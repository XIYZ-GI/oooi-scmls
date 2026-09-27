"""混合批次按实际几何与轨迹验收，功能标签不能代替机制证据。"""

from ..front_output import inspect as inspect_front
from ..regular_admission import inspect_physics, inspect_shape
from ..verification import verify_pulls
from ..feedback_ablation import verify_redstone
from ...regular_generator_v2.compactness import describe_compactness
from ...regular_generator_v2.composite_admission import output_distances
from ...regular_generator_v2.solid_regions import describe_regions
from .mixed_profiles import SIZE_BANDS, DENSITY_BANDS


def describe(row):
    compact = describe_compactness(row)
    regions = describe_regions(row['task']['targets'])
    zs = [b['position']['z'] for b in row['proposal']['blocks']]
    return dict(compactness=compact, actual_depth=max(zs)-min(zs)+1,
                groups=len(regions['group_counts']),
                max_simultaneous=regions['max_simultaneous'],
                simultaneous_rectangle=regions['largest_simultaneous_area'],
                partitioned_rectangle=regions['largest_partitioned_area'])


def shape_issue(row, requirements):
    metrics = describe(row)
    compact = metrics['compactness']
    size = SIZE_BANDS[requirements['size']]
    short, long = sorted((compact['width'], compact['height']))
    if short < size['min_side'] or not size['min_long'] <= long <= size['max_long']:
        return '实际截面不在本专项尺寸档位'
    lo, hi = DENSITY_BANDS[requirements['density']]
    if compact['target_density'] < lo or hi is not None and compact['target_density'] >= hi:
        return '实际目标密度不在本专项区间'
    if metrics['groups'] < requirements['min_groups']:
        return '实际时序组未达到本专项下限'
    _, reason = inspect_front(row)
    if reason:
        return reason
    rectangle = requirements.get('rectangle')
    if rectangle:
        area = (metrics['simultaneous_rectangle'] if rectangle == 'simultaneous'
                else metrics['partitioned_rectangle'] if rectangle == 'partitioned'
                else max(metrics['simultaneous_rectangle'], metrics['partitioned_rectangle']))
        if area < 12 or metrics['max_simultaneous'] < 11:
            return '缺少十二点实心矩形或十一点以上同推组'
    if requirements.get('combined'):
        _, reason = inspect_shape(row, dict(density_goal=.72, min_groups=4,
                                            min_simultaneous=11, solid_timing='either'))
        if reason:
            return reason
    return ''


def physics(row, mechanisms):
    _, reason = inspect_front(row)
    if reason:
        return None, reason
    if row['task']['depth'] >= 4 and row['family'] == '推拉结合多时序':
        return inspect_physics(row, mechanisms)
    distances, reason = output_distances(row)
    if reason:
        return None, reason
    pulls, reason = verify_pulls({**row, 'mechanisms': mechanisms})
    if reason:
        return None, reason
    redstone, reason = verify_redstone(row)
    if reason:
        return None, reason
    return dict(output_distances=distances, pull_ablation=pulls,
                redstone_ablation=redstone), ''


def mechanism_flags(row):
    mechanisms = row.get('mechanisms', {})
    audit = mechanisms.get('mechanism_audit', {})
    operations = [op for op in audit.get('operations', []) if not op['external']]
    declared = set(row.get('construction', {}).get('feedback_growth', []))
    redstone_ok = bool(row.get('redstone_ablation')) and all(
        c.get('accepted') is False for c in row['redstone_ablation'])
    pulls_ok = bool(row.get('pull_ablation')) and all(
        c.get('accepted') is False or c.get('lost_target_count', 0) > 0
        for c in row['pull_ablation'])
    next_source = redstone_ok and any(s['source_kind'] == 'redstone_block'
        and s.get('source_group') == op['index'] for op in operations for s in op['sources'])
    recall = redstone_ok and pulls_ok and any(op['kind'] == 'pull' and any(
        m['kind'] == 'redstone_block' for m in op['members']) for op in operations)
    half = pulls_ok and any(op['driver_moved_after_work'] for op in operations)
    return [kind for kind, valid in (('next_source', next_source), ('redstone_recall', recall),
                                   ('half_engine', half)) if valid and kind in declared]


def admission(row, profile):
    reason = shape_issue(row, profile['requirements'])
    if reason:
        return reason
    metrics = describe(row)
    if metrics['actual_depth'] != profile['depth'] or row['family'] != profile['category']:
        return '实际厚度或类别不符合专项'
    task, evaluation = row['task'], row.get('evaluation', {})
    if task['rounds'] != 3 or task['load_blocks'] != 10 or not evaluation.get('accepted') or len(evaluation.get('rounds', [])) != 3:
        return '缺少三轮十负载验收'
    if profile['depth'] >= 4 and profile['category'] == '推拉结合多时序':
        from ..layered_evidence import inspect_layers
        _, reason = inspect_layers(row, row['mechanisms'])
        if reason:
            return reason
    flags = mechanism_flags(row)
    requested = profile['requirements'].get('mechanism')
    if requested == '组合':
        if 'half_engine' not in flags or not {'next_source', 'redstone_recall'} & set(flags):
            return '没有同时验证红石应用与半动机'
    elif requested and requested not in flags:
        return '缺少指定红石或半动机的实际机制证据'
    row['batch_metrics'] = dict(metrics, verified_mechanisms=flags,
                               size_band=profile['requirements']['size'],
                               density_band=profile['requirements']['density'])
    return ''

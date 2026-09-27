"""多尺寸展示的联合检查；物理通过不能替代目标密度、时序和形态多样性。"""

from collections import Counter

from .campaign import POLICY, SIZES
from .compactness import describe_compactness
from .composite_admission import output_distances
from .solid_regions import describe_regions, select_regions
from ..structure_generator.layered_evidence import inspect_layers


def candidate_report(row):
    targets = row['task']['targets']
    compact = describe_compactness(row)
    issues = []
    size = tuple(sorted((compact['width'], compact['height'])))
    if (size[0] < POLICY['min_side'] or size[1] > POLICY['max_side']
            or compact['area'] > POLICY['max_area']):
        issues.append('完整本体截面不在中小尺寸档位内')
    if compact['target_density'] < POLICY['min_density']:
        issues.append('整机目标密度不足72%')
    if compact['largest_empty_area'] > POLICY['max_empty_area']:
        issues.append('连续无目标矩形超过四格')
    if compact['max_distance_to_target'] is None or compact['max_distance_to_target'] > POLICY['max_distance']:
        issues.append('存在离最近目标超过一格的位置')
    counts = Counter(t['order'] for t in targets)
    if len(counts) < POLICY['min_groups']:
        issues.append('时序组不足四组')
    regions = describe_regions(targets)
    requirements = row.get('requested_sampling', {}).get('options', row.get('requested_options', {}))
    mode = requirements.get('solid_timing', POLICY['solid_timing'])
    selected = select_regions(regions, mode, POLICY['min_simultaneous'],
                              requirements.get('simultaneous_scope', POLICY['simultaneous_scope']))
    count = regions['min_simultaneous'] if selected['scope'] == 'every' else regions['max_simultaneous']
    if count < POLICY['min_simultaneous']:
        issues.append('缺少符合要求的十一点以上同推组')
    area = selected['largest_area']
    if area < compact['area']*POLICY['min_solid_fraction']:
        issues.append('满足时序类型的实心目标区不足截面四成')
    depth = [b['position']['z'] for b in row['proposal']['blocks']]
    if not depth or not 2 <= max(depth)-min(depth)+1 <= POLICY['max_depth']:
        issues.append('实际厚度不在二至六格')
    if not targets:
        distances = None
        issues.append('没有目标')
    else:
        distances, reason = output_distances(row)
        if reason:
            issues.append(reason)
        from ..structure_generator.front_output import inspect as inspect_front
        _, reason = inspect_front(row)
        if reason:
            issues.append(reason)
    evidence = row.get('mechanisms', {})
    links = evidence.get('links', [])
    if (not links or not evidence.get('functional_pulls')
            or evidence.get('functional_pulls', 0)+evidence.get('functional_pushes', 0) != len(links)
            or any(e.get('kind') not in ('push', 'pull') or e.get('rounds') != 3
                   or not e.get('dependent_outputs') for e in links)):
        issues.append('缺少内部推拉连接的三轮有效运动证据')
    layers, reason = inspect_layers(row, evidence) if depth else (None, '没有分层本体')
    if reason:
        issues.append('分层证据不足：'+reason)
    evaluation = row.get('evaluation', {})
    if (not evaluation.get('accepted') or len(evaluation.get('rounds', [])) != 3
            or row['task'].get('load_blocks') != 10):
        issues.append('缺少三轮十负载通过记录')
    controls = row.get('pull_ablation', [])
    if not controls or any(not (c.get('lost_target_count', 0) > 0 or c.get('accepted') is False) for c in controls):
        issues.append('缺少回拉消融对照')
    return dict(id=row.get('id'), accepted=not issues, issues=issues,
                size=list(size), compactness=compact, groups=len(counts),
                max_simultaneous=max(counts.values(), default=0),
                largest_solid_area=area, solid_regions=regions, selected_regions=selected,
                output_distances=distances, layer_evidence=layers)


def batch_report(rows):
    reports = [candidate_report(row) for row in rows]
    issues = []
    if not rows or any(not r['accepted'] for r in reports):
        issues.append('包含未达到联合标准的候选，或没有候选')
    if len({tuple(r['size']) for r in reports}) < POLICY['min_size_kinds']:
        issues.append('展示批次不足三种尺寸')
    # 旧构造模式内挪动接口、换材料、改变宽度不算新的连接方式。
    modes = {r.get('plan', {}).get('mode') for r in rows}
    if None in modes or len(modes) < 2:
        issues.append('展示批次缺少不同连接构造，单一模式尺寸变体不能充数')
    return dict(accepted=not issues, issues=issues, candidates=reports,
                policy=POLICY, sizes=[list(s) for s in SIZES])

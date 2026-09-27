"""独立识别多个大实心区、非矩形目标与每列真实输出活塞距离。"""

from collections import Counter

from .metrics import describe_targets
from .rectangles import cells, rectangles


def output_distances(row):
    columns = {}
    for item in row['proposal']['blocks']:
        p = item['position']
        columns.setdefault((p['x'], p['y']), []).append(item)
    distances = []
    for target in row['task']['targets']:
        behind = [b for b in columns.get((target['x'], target['y']), [])
                  if b['position']['z'] < target['z']]
        if not behind:
            return None, '目标列缺少输出活塞'
        front = max(behind, key=lambda b: b['position']['z'])
        if front['block']['kind'] not in ('piston', 'sticky_piston') or front['block']['facing'] != 'positive_z':
            return None, '目标列最前方方块不是朝前输出活塞'
        distance = target['z']-front['position']['z']
        if not 1 <= distance <= 3:
            return None, '输出活塞与目标点距离超过三格'
        distances.append(distance)
    return dict(min=min(distances), max=max(distances), counts=dict(Counter(distances))), ''


def composite_issue(row):
    targets, plan = row['task']['targets'], row['plan']
    metrics = describe_targets(targets)
    # 只保留不包含在其他矩形内的极大矩形，再按不重叠选择独立区域。
    candidates = rectangles({(t['x'], t['y']) for t in targets}, min_area=24)
    maximal = []
    for rectangle in candidates:
        points = cells(rectangle)
        if not any(points <= cells(other) for other in maximal):
            maximal.append(rectangle)
    independent, used = [], set()
    for rectangle in maximal:
        points = cells(rectangle)
        if not points & used:
            independent.append(rectangle)
            used.update(points)
    metrics.update(independent_rectangles=independent, rectangle_count=len(independent),
                   max_simultaneous=max(Counter(t['order'] for t in targets).values(), default=0))
    distances, reason = output_distances(row)
    if reason:
        return metrics, reason
    metrics['output_distances'] = distances
    if len(independent) < plan['branches']:
        return metrics, '独立大实心矩形不足，不能用单矩形拆分充数'
    if metrics['strip_only_points'] < 4 or metrics['outside_regular_points'] < 2:
        return metrics, '缺少矩形外条带、折线或散点组合'
    if metrics['max_simultaneous'] < 2*plan['branches'] or metrics['groups'] < 3:
        return metrics, '复合结构缺少同时输出或多个时序'
    if plan['mode'] == 'hybrid_pull':
        same_area = max((v['largest_rectangle']['area'] if v['largest_rectangle'] else 0)
                        for v in metrics['same_time'].values())
        if same_area < 24:
            return metrics, '混合结构缺少至少二十四点的实心同推区'
        metrics['largest_simultaneous_rectangle_area'] = same_area
    signature = lambda values: sorted((t['x'], t['y'], t['z'], t['order']) for t in values)
    if signature(targets) != signature(plan['expected_targets']):
        return metrics, '目标布局或时序与构造前计划不一致'
    if not 2 <= row['task']['depth'] <= 6:
        return metrics, '复合结构厚度超出二至六格'
    return metrics, ''

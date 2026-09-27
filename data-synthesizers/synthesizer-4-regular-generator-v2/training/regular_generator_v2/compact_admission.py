"""紧凑专项同时检查几何组合、整机密度、中央空区和固定时序。"""

from collections import Counter

from .compactness import compactness_issue, describe_compactness
from .composite_admission import output_distances
from .metrics import describe_targets
from .rectangles import cells, rectangles


def compact_issue(row):
    targets = row['task']['targets']
    metrics = describe_targets(targets)
    metrics['compactness'] = describe_compactness(row)
    reason = compactness_issue(metrics['compactness'])
    if reason:
        return metrics, reason
    distances, reason = output_distances(row)
    if reason:
        return metrics, reason
    metrics['output_distances'] = distances
    selected, covered = [], set()
    for rectangle in rectangles({(t['x'], t['y']) for t in targets}, min_area=24):
        area = cells(rectangle)
        if not area & covered:
            selected.append(rectangle)
            covered |= area
    metrics.update(independent_rectangles=selected, rectangle_count=len(selected),
                   max_simultaneous=max(Counter(t['order'] for t in targets).values(), default=0),
                   largest_simultaneous_rectangle_area=max(
                       (v['largest_rectangle']['area'] if v['largest_rectangle'] else 0)
                       for v in metrics['same_time'].values()))
    if len(selected) < 2 or metrics['largest_simultaneous_rectangle_area'] < 24:
        return metrics, '紧凑结构缺少多个大实心区域及密集同时输出'
    if metrics['groups'] < 3 or metrics['outside_regular_points'] < 4:
        return metrics, '紧凑结构缺少分时序或非矩形目标'
    signature = lambda values: sorted((t['x'], t['y'], t['z'], t['order']) for t in values)
    if signature(targets) != signature(row['plan']['expected_targets']):
        return metrics, '紧凑目标布局或时序偏离构造前计划'
    if not 2 <= row['task']['depth'] <= 6:
        return metrics, '紧凑结构厚度超出预算'
    return metrics, ''

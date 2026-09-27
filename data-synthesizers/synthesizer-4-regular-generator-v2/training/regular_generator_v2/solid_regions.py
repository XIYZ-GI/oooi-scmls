"""分别核对同刻矩形和矩形内分时序，保留区域内、外的同推数量。"""

from collections import Counter

from .patterns import timing_pattern
from .rectangles import cells, rectangles


TIMING_MODES = ('simultaneous', 'partitioned', 'either')


def describe_regions(targets):
    orders = {(t['x'], t['y']): t['order'] for t in targets}
    if len(orders) != len(targets):
        raise ValueError('同一目标列重复，不能靠纵深重复计算实心面积')
    groups = Counter(orders.values())
    simultaneous = []
    for order in sorted(groups):
        simultaneous.extend(dict(r, order=order) for r in rectangles(
            {p for p, value in orders.items() if value == order}))
    simultaneous.sort(key=lambda r: (-r['area'], r['order'], r['x'], r['y']))
    maximal = []
    for rectangle in rectangles(orders):
        region = cells(rectangle)
        if any(region <= covered for _, covered in maximal):
            continue
        counts = Counter(orders[p] for p in region)
        maximal.append((dict(rectangle, groups=dict(sorted(counts.items())),
                             group_count=len(counts), max_simultaneous=max(counts.values()),
                             min_simultaneous=min(counts.values()),
                             timing=timing_pattern(rectangle, orders)), region))
    partitioned = [r for r, _ in maximal if r['group_count'] > 1]
    return dict(group_counts=dict(sorted(groups.items())),
                max_simultaneous=max(groups.values(), default=0),
                min_simultaneous=min(groups.values(), default=0),
                simultaneous=simultaneous, partitioned=partitioned,
                largest_simultaneous_area=max((r['area'] for r in simultaneous), default=0),
                largest_partitioned_area=max((r['area'] for r in partitioned), default=0),
                largest_geometric_area=max((r['area'] for r, _ in maximal), default=0))


def select_regions(report, mode='either', minimum=11, scope='any'):
    """同推数量按整机分组检查，主副矩形分别保留实际面积与组内数量。"""
    if mode not in TIMING_MODES or scope not in ('any', 'every'):
        raise ValueError('未知的实心区域时序模式或同推组范围')
    if minimum < 11:
        raise ValueError('同一时序的目标门槛必须超过十点')
    selected = []
    count = report['max_simultaneous'] if scope == 'any' else report['min_simultaneous']
    if count >= minimum and mode in ('simultaneous', 'either'):
        selected.extend(dict(r, mode='simultaneous') for r in report['simultaneous']
                        if r['area'] >= 4)
    if count >= minimum and mode in ('partitioned', 'either'):
        selected.extend(dict(r, mode='partitioned') for r in report['partitioned'])
    selected.sort(key=lambda r: (-r['area'], r['x'], r['y'], r['mode']))
    independent, covered = [], set()
    for rectangle in selected:
        points = cells(rectangle)
        if not points & covered:
            independent.append(rectangle)
            covered.update(points)
    return dict(mode=mode, scope=scope, minimum=minimum,
                group_requirement_met=count >= minimum,
                qualifying=selected, independent=independent,
                largest_area=max((r['area'] for r in selected), default=0),
                covered_points=len(covered))

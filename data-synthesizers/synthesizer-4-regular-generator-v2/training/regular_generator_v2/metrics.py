"""面向二维目标投影的实心、条带、分组和外围点统计。"""

from .config import MIN_AREA, MIN_STRIP
from .patterns import timing_pattern
from .rectangles import cells, rectangles


def describe_targets(targets, min_area=MIN_AREA, min_strip=MIN_STRIP):
    if min_area < 4 or min_strip < 2:
        raise ValueError('实心矩形面积至少四格，连续条带至少两格')
    if any(type(t.get(k)) is not int for t in targets for k in ('x', 'y', 'order')):
        raise ValueError('目标投影坐标与时序必须为整数')
    orders = {(t['x'], t['y']): t['order'] for t in targets}
    if len(orders) != len(targets):
        raise ValueError('同一目标列重复，不能靠不同纵深重复计算密度')
    if any(order < 1 for order in orders.values()):
        raise ValueError('时序组必须为正整数')
    if not targets:
        return dict(targets=0, groups=0, largest_rectangle=None, solid_coverage=0.,
                    solid_points=0, outside_solid_points=0, largest_strip=None,
                    strip_coverage=0., regular_coverage=0., outside_regular_points=0,
                    strip_only_points=0, same_time={}, rectangle_timing=None)
    points = set(orders)
    full = rectangles(points)
    solid = [r for r in full if r['area'] >= min_area]
    covered = set().union(*(cells(r) for r in solid)) if solid else set()
    strips = [r for r in rectangles(points, min_short=1, min_area=min_strip)
              if min(r['width'], r['height']) == 1]
    # 大实心矩形中的行同样属于连续条带，不要求它是纵向极大的一行。
    for axis in (0, 1):
        for fixed in sorted({p[1-axis] for p in points}):
            line = {(p[axis], 0) for p in points if p[1-axis] == fixed}
            for r in rectangles(line, min_short=1, min_area=min_strip):
                strips.append(dict(x=r['x'] if axis == 0 else fixed,
                                   y=fixed if axis == 0 else r['x'],
                                   width=r['width'] if axis == 0 else 1,
                                   height=1 if axis == 0 else r['width'], area=r['area']))
    strips.sort(key=lambda r: (-r['area'], r['x'], r['y']))
    strip_points = set().union(*(cells(r) for r in strips)) if strips else set()
    same_time = {}
    for group in sorted(set(orders.values())):
        selected = {p for p, value in orders.items() if value == group}
        shapes = rectangles(selected)
        lines = rectangles(selected, min_short=1, min_area=min_strip)
        same_time[str(group)] = dict(targets=len(selected), largest_rectangle=shapes[0] if shapes else None,
                                    largest_filled_region=lines[0] if lines else None)
    largest = full[0] if full else None
    xs, ys = zip(*points)
    return dict(targets=len(points), groups=len(same_time),
                target_bbox_density=len(points)/((max(xs)-min(xs)+1)*(max(ys)-min(ys)+1)),
                largest_rectangle=largest, solid_points=len(covered),
                solid_coverage=len(covered)/len(points), outside_solid_points=len(points-covered),
                largest_strip=strips[0] if strips else None, strip_coverage=len(strip_points)/len(points),
                regular_coverage=len(covered | strip_points)/len(points),
                outside_regular_points=len(points-covered-strip_points),
                strip_only_points=len(strip_points-covered),
                same_time=same_time,
                rectangle_timing=timing_pattern(largest, orders) if largest else None)

"""按完整结构截面衡量目标覆盖及内部空白，不用局部实心率替代整体密度。"""

from .rectangles import rectangles


def describe_compactness(row):
    points = {(t['x'], t['y']) for t in row['task']['targets']}
    body = {(b['position']['x'], b['position']['y']) for b in row['proposal']['blocks']}
    occupied = points | body
    if not occupied:
        return dict(width=0, height=0, area=0, target_density=0., largest_empty_area=0,
                    largest_empty_rectangle=None, max_distance_to_target=None)
    x0, x1 = min(p[0] for p in occupied), max(p[0] for p in occupied)
    y0, y1 = min(p[1] for p in occupied), max(p[1] for p in occupied)
    section = {(x, y) for x in range(x0, x1+1) for y in range(y0, y1+1)}
    # 空白指没有目标的截面格，即使其中堆有连接方块，也必须算作无输出区。
    empty = section-points
    blanks = rectangles(empty, min_short=1, min_area=1)
    largest = blanks[0] if blanks else None
    return dict(width=x1-x0+1, height=y1-y0+1, area=len(section),
                target_density=len(points)/len(section),
                largest_empty_area=largest['area'] if largest else 0,
                largest_empty_rectangle=largest,
                max_distance_to_target=max((min(abs(x-a)+abs(y-b) for a, b in points)
                                            for x, y in section), default=0) if points else None,
                blocks_per_target=len(row['proposal']['blocks'])/len(points) if points else None)


def compactness_issue(metrics):
    from .config import COMPACT_LIMITS
    if max(metrics['width'], metrics['height']) > COMPACT_LIMITS['side'] or metrics['area'] > COMPACT_LIMITS['area']:
        return '结构截面尺寸超过紧凑预算'
    if metrics['target_density'] < COMPACT_LIMITS['density']:
        return '完整结构截面的目标覆盖率不足'
    if metrics['largest_empty_area'] > COMPACT_LIMITS['empty_area']:
        return '结构内部连续无目标区域过大'
    if metrics['max_distance_to_target'] > COMPACT_LIMITS['distance']:
        return '连接区域离有效输出目标过远'
    return ''

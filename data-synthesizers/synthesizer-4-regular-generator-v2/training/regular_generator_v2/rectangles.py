"""按完整整数格枚举实心矩形；边框、缺口和斜邻不能充当填满区域。"""


def rectangles(points, min_short=2, min_area=4):
    """返回纵向不可再延长的实心矩形，坐标包含两端；保留横向子区间供覆盖统计。"""
    points = set(points)
    if not points:
        return []
    xs, ys = zip(*points)
    result = []
    for left in range(min(xs), max(xs)+1):
        rows = set(range(min(ys), max(ys)+1))
        for right in range(left, max(xs)+1):
            rows &= {y for x, y in points if x == right}
            if not rows:
                break
            start = previous = None
            for y in [*sorted(rows), max(ys)+2]:
                if previous is not None and y != previous+1:
                    width, height = right-left+1, previous-start+1
                    if min(width, height) >= min_short and width*height >= min_area:
                        result.append(dict(x=left, y=start, width=width, height=height,
                                           area=width*height))
                    start = None
                if start is None:
                    start = y
                previous = y
    return sorted(result, key=lambda r: (-r['area'], -min(r['width'], r['height']), r['x'], r['y']))


def cells(rectangle):
    return {(x, y) for x in range(rectangle['x'], rectangle['x']+rectangle['width'])
            for y in range(rectangle['y'], rectangle['y']+rectangle['height'])}

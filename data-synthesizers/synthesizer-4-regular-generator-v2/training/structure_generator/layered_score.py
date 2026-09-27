"""按请求分别比较同刻、区内分时序实心区域和整机覆盖。"""

from ..regular_generator_v2.solid_regions import describe_regions, select_regions


def score(layout, mode='either'):
    targets = [dict(x=v['piston'][0], y=v['piston'][1], order=v['tick']) for v in layout.outputs]
    report = describe_regions(targets)
    selected = select_regions(report, mode)
    xs, ys = zip(*(p[:2] for p in layout.blocks))
    area = (max(xs)-min(xs)+1)*(max(ys)-min(ys)+1)
    # 尚未凑齐十一点时仍提供连续的生长方向，但不能据此通过最终准入。
    potential = (report['largest_simultaneous_area'] if mode == 'simultaneous'
                 else report['largest_geometric_area'])
    return (selected['largest_area']/area,
            (len(layout.outputs)+3*potential)/area, len(layout.outputs), -area)

"""按实际厚度定义分层窗口；五格的交错窗口由运动组归属区分。"""


LAYERED_DEPTHS = (4, 5, 6)


def bands(depth):
    if depth not in LAYERED_DEPTHS:
        raise ValueError('分层构造支持四、五、六格厚度')
    starts = (0, 2) if depth == 4 else (0, 2, depth-2)
    names = ('后层', '前层') if depth == 4 else ('后层', '中层', '前层')
    return [dict(name=name, start=start, depths=[start, start+1])
            for name, start in zip(names, starts)]


def describe(depth, origin=0):
    return [dict(band, depths=[z+origin for z in band['depths']]) for band in bands(depth)]


def owner(row, driver):
    """交错处先使用构造时的运动组归属，同一驱动只属于一层。"""
    origin = row['proposal']['push']['z']
    scheme = bands(row['task']['depth'])
    possible = [b['start'] for b in scheme if origin+b['start'] <= driver['z'] <= origin+b['start']+1]
    explicit = {op['layer'] for op in row.get('construction', {}).get('operations', [])
                if 'layer' in op and driver in op['added'] and op['layer'] in possible}
    if len(explicit) > 1:
        return None
    return next(iter(explicit)) if explicit else max(possible, default=None)

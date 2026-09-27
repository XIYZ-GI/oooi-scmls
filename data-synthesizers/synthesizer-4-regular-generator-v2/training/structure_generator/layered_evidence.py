"""按厚度与运动组归属核对每层有效推拉，交错窗口不重复计算驱动。"""

from .layer_scheme import LAYERED_DEPTHS, describe, owner


def inspect_layers(row, mechanisms):
    depths = [b['position']['z'] for b in row['proposal']['blocks']]
    low, high = min(depths), max(depths)
    depth = high-low+1
    if depth not in LAYERED_DEPTHS or depth != row['task']['depth']:
        return None, '分层结构的实际厚度必须与四至六格需求一致'
    report = []
    links = mechanisms.get('links', [])
    outputs = mechanisms.get('output_pushes', [])
    scheme = describe(depth, low)
    for band in scheme:
        name, start = band['name'], band['depths'][0]
        strict = row.get('construction', {}).get('output_policy') == 'front_only'
        candidates = links if strict and band != scheme[-1] else [*links, *outputs]
        valid = [e for e in candidates
                 if start <= e['driver']['z'] <= start+1
                 and (depth == 4 or owner(row, e['driver']) == band['start'])
                 and e.get('rounds') == 3 and e.get('dependent_outputs', 0) > 0]
        pushes = [e['driver'] for e in valid if e['kind'] == 'push']
        pulls = [e['driver'] for e in valid if e['kind'] == 'pull']
        report.append(dict(name=name, depths=[start, start+1], pushes=pushes, pulls=pulls))
        if not pushes or not pulls:
            return report, name+'缺少三轮实际有效的推动或回拉'
    return report, ''

"""固定目标形状与时序的准入；形态成功不能替代三轮物理成功。"""

from .config import MIN_AREA
from .metrics import describe_targets
from .rectangles import cells


def shape_issue(row):
    if row['plan']['mode'] == 'compact_pull':
        from .compact_admission import compact_issue
        return compact_issue(row)
    if row['plan']['mode'] in ('pull_composite', 'hybrid_pull'):
        from .composite_admission import composite_issue
        return composite_issue(row)
    task, plan = row['task'], row['plan']
    metrics = describe_targets(task['targets'])
    core = plan['core']
    points = {(t['x'], t['y']): t['order'] for t in task['targets']}
    required = cells(core)
    if core['width']*core['height'] < MIN_AREA or not required <= points.keys():
        return metrics, '预定实心矩形存在缺口或面积不足'
    outside = set(points)-required
    if len(outside) != plan.get('scatter_count', int(plan['scatter'])):
        return metrics, '外围目标数量与计划不符'
    if outside and min(abs(x-a)+abs(y-b) for x, y in outside for a, b in required) < 2:
        return metrics, '外围目标没有与实心核心隔开'
    offset = core['x']
    for i, width in enumerate(plan['widths']):
        order = 1 if plan['mode'] == 'simultaneous' else i % 2+1 if plan['mode'] == 'parallel_staged' else i+1
        if any(points[x, y] != order for x in range(offset, offset+width)
               for y in range(core['y'], core['y']+core['height'])):
            return metrics, '实心区域的预定时序条带不符'
        offset += width
    for p in outside:
        expected = (1 if plan['mode'] == 'simultaneous' or p[0] < core['x'] else
                    2 if plan['mode'] == 'parallel_staged' else len(plan['widths']))
        if points[p] != expected:
            return metrics, '外围目标的预定时序不符'
    if metrics['solid_coverage'] < .75:
        return metrics, '实心区域覆盖不足四分之三'
    return metrics, ''

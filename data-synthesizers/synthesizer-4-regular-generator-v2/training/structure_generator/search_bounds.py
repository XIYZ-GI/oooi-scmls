"""补位阶段的保守容量上界；只排除剩余生长也无法满足的需求。"""

from .config import LIMITS, MATERIALS, SIDES, VECTORS
from .geometry import add
from .power import sockets
from .front_output import allowed as output_allowed


def period_if_in_bounds(layout):
    """预筛只需要尺寸与周期，不必反复构造整份归一化任务。"""
    xs, ys = zip(*((p[0], p[1]) for p in layout.blocks))
    width, height = max(xs)-min(xs)+1, max(ys)-min(ys)+1
    if width > LIMITS['width'] or height > LIMITS['height'] or width*height*(layout.high-layout.low+1) > LIMITS['volume']:
        return None
    return max(48, max((v['tick'] for v in layout.outputs), default=8)+12)


def completion_issue(layout, options, dense):
    """此阶段只增加输出活塞和侧向观察者，不增加材料块或删除已有块。"""
    positions = set(layout.blocks)
    candidates = {p for p,kinds in sockets(layout.blocks).items() if 'push' in kinds}
    if dense:
        # 即使把所有材料都允许补供电，仍然不够的情况才拒绝。
        for p,b in layout.blocks.items():
            if b['kind'] not in MATERIALS:
                continue
            for direction in SIDES:
                observer = add(p,direction)
                if layout.free(observer):
                    positions.add(observer)
                    candidates.update(add(p,d) for d in VECTORS.values() if d != (0,0,-1))
    else:
        candidates.clear()
    columns = {v['piston'][:2] for v in layout.outputs}
    for p in candidates:
        if output_allowed(layout, p) and layout.free(p) and not any(q[:2] == p[:2] and q[2] > p[2] for q in layout.blocks):
            positions.add(p)
            columns.add(p[:2])
    width = max(p[0] for p in positions)-min(p[0] for p in positions)+1
    height = max(p[1] for p in positions)-min(p[1] for p in positions)+1
    if max(width,height) < options.get('min_long_side',0) or min(width,height) < options.get('min_short_side',0):
        return '实际截面未达到本批尺寸下限'
    count = min(32,len(columns))
    if count < options.get('target_goal',3):
        return '目标数量未达到本批下限'
    area = ((max(p[0] for p in layout.blocks)-min(p[0] for p in layout.blocks)+1)*
            (max(p[1] for p in layout.blocks)-min(p[1] for p in layout.blocks)+1))
    if count/area < options.get('density_goal',0):
        return '目标密度未达到本批下限'
    return ''

"""在原随机供电生长候选中优先选择可形成连续实心输出的局部分支。"""

from .growth import supply as original_supply
from .power import sockets
from .side_growth import supply as side_supply
from ..regular_generator_v2.rectangles import rectangles
from .front_output import allowed as output_allowed


def potential(layout, added):
    """只估计候选空位；这些位置仍须经过原搜索的逐分支物理验证。"""
    points = {v['piston'][:2] for v in layout.outputs}
    for p, kinds in sockets(layout.blocks, added).items():
        if ('push' in kinds and layout.free(p) and output_allowed(layout, p) and
                not any(q[:2] == p[:2] and q[2] > p[2] for q in layout.blocks)):
            points.add(p[:2])
    body = {p[:2] for p in layout.blocks} | points
    area = ((max(p[0] for p in body)-min(p[0] for p in body)+1)*
            (max(p[1] for p in body)-min(p[1] for p in body)+1))
    squares = sum(all((x+dx, y+dy) in points for dx, dy in ((1, 0), (0, 1), (1, 1)))
                  for x, y in points)
    if getattr(layout, 'large_regions', False):
        regions = rectangles(points)
        largest = regions[0]['area'] if regions else 0
        return (len(points)+3*largest)/area, largest, len(points), -area
    # 实心四格优先，但需与完整截面覆盖共同计分，避免大跨度局部矩形。
    return (len(points)+2*squares)/area, len(points), -area


def supply(layout, rng, anchor, style, compact, trials=4):
    saved = layout.checkpoint()
    candidates = []
    for _ in range(trials):
        layout.restore(saved)
        if rng.random() < .65:
            added = side_supply(layout, rng, anchor, budget=8)
        else:
            added = original_supply(layout, rng, anchor, style, budget=8, compact=compact)
        if added and added <= layout.blocks.keys():
            candidates.append((potential(layout, added), layout.checkpoint(), added))
    if not candidates:
        layout.restore(saved)
        return None
    # 留出随机探索，不能把相同局部高分形态变成唯一生长路线。
    selected = rng.choice(candidates) if rng.random() < .25 else max(candidates, key=lambda v: v[0])
    layout.restore(selected[1])
    return selected[2]

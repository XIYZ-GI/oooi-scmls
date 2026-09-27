"""同时扇出与分段接力两类薄结构构造；目标与时序在模拟前固定。"""

from .config import MATERIALS
from .layout import Layout
from .slabs import scattered_output, slab


def build(plan):
    if plan['mode'] == 'compact_pull':
        from .compact import build_compact
        return build_compact(plan)
    if plan['mode'] == 'hybrid_pull':
        from .hybrid import build_hybrid
        return build_hybrid(plan)
    if plan['mode'] == 'pull_composite':
        from .composite import build_composite
        return build_composite(plan)
    if plan.get('rows', 2) == 3:
        from .three_rows import build_three_rows
        return build_three_rows(plan)
    if plan['mode'] == 'parallel_staged':
        from .parallel_stages import build_parallel_stages
        return build_parallel_stages(plan)
    layout = Layout()
    widths = plan['widths']
    flips = plan.get('flips', [False]*len(widths))
    anchors = plan.get('anchors', [w//2 for w in widths])
    simultaneous = plan['mode'] == 'simultaneous'
    left, entries = 0, []
    for i, width in enumerate(widths):
        before = set(layout.blocks)
        material = MATERIALS[(i+plan.get('material_phase', 0)) % 2]
        z = 0 if simultaneous else i
        order = 1 if simultaneous else i+1
        y = int(flips[i])
        slab(layout, left, width, z, material, order, flips[i])
        if plan.get('scatter') and i == 0:
            scattered_output(layout, left, z, material, order, flipped=flips[i])
        if plan.get('scatter_count', int(plan.get('scatter', False))) == 2 and i == len(widths)-1:
            scattered_output(layout, left+width-1, z, material, order, side=1, flipped=flips[i])
        if not simultaneous and i < len(widths)-1:
            if flips[i] != flips[i+1]:
                raise ValueError('接力带的供电侧必须一致')
            x = left+width-1
            layout.put(x, y, z-1, material)
            layout.put(x, 2 if flips[i] else -1, z-1, 'observer',
                       'negative_y' if flips[i] else 'positive_y')
            layout.put(x+1, y, z-1, 'piston')
        anchor = (left+anchors[i], y, z)
        layout.record_group(before, anchor, order)
        entries.append(anchor)
        left += width
    if simultaneous and len(widths) > 1:
        before = set(layout.blocks)
        if plan.get('side_root'):
            if any(flips):
                raise ValueError('侧置扇出要求供电侧一致')
            for x in range(min(p[0] for p in entries), max(p[0] for p in entries)+1):
                layout.put(x, -1, -2, MATERIALS[plan.get('material_phase', 0)])
            for x, _, _ in entries:
                layout.put(x, -2, -2, 'observer', 'positive_y')
                layout.put(x, 0, -2, 'piston')
            layout.push = (entries[len(entries)//2][0], -1, -2)
            layout.record_group(before, layout.push, 0)
            return layout.pack(plan)
        spine = set()
        # 输入点沿截面连成一棵短树，供电观察者置于树后，避免占用各行接口。
        base_y = plan.get('spine_y', 0)
        for x in range(min(p[0] for p in entries), max(p[0] for p in entries)+1):
            spine.add((x, base_y))
        for x, y, _ in entries:
            for step in range(min(y, base_y), max(y, base_y)+1):
                spine.add((x, step))
        rear_observers = plan.get('rear_observers', False)
        root_z = -4 if rear_observers else -3
        for x, y in sorted(spine):
            layout.put(x, y, root_z, MATERIALS[plan.get('material_phase', 0)])
        for x, y, _ in entries:
            if rear_observers:
                layout.put(x, y, -3, 'observer')
            else:
                layout.put(x, y-1 if base_y <= y else y+1, -3, 'observer',
                           'positive_y' if base_y <= y else 'negative_y')
            layout.put(x, y, -2, 'piston')
        layout.push = (entries[len(entries)//2][0], base_y, root_z)
        layout.record_group(before, layout.push, 0)
    elif simultaneous:
        layout.push = entries[0]
    else:
        layout.push = (widths[0]-1, int(flips[0]), -1)
    return layout.pack(plan)

"""在同一实心矩形中并行启动多条接力，形成重复的时序带。"""

from .config import MATERIALS
from .layout import Layout
from .slabs import scattered_output, slab


def build_parallel_stages(plan):
    layout = Layout()
    left, entries = 0, []
    for i, width in enumerate(plan['widths']):
        before = set(layout.blocks)
        z = i % 2
        material = MATERIALS[(i+plan.get('material_phase', 0)) % 2]
        slab(layout, left, width, z, material, z+1)
        if plan.get('scatter') and i == 0:
            scattered_output(layout, left, z, material, 1)
        if plan.get('scatter_count') == 2 and i == len(plan['widths'])-1:
            scattered_output(layout, left+width-1, z, material, 2, side=1)
        if i % 2 == 0:
            x = left+width-1
            layout.put(x, 0, -1, material)
            layout.put(x, -1, -1, 'observer', 'positive_y')
            layout.put(x+1, 0, -1, 'piston')
            entries.append((x, 0, -1))
        layout.record_group(before, (left, 0, z), z+1)
        left += width
    before = set(layout.blocks)
    for x in range(min(p[0] for p in entries), max(p[0] for p in entries)+1):
        layout.put(x, -1, -3, MATERIALS[plan.get('material_phase', 0)])
    for x, _, _ in entries:
        layout.put(x, -2, -3, 'observer', 'positive_y')
        layout.put(x, 0, -3, 'piston')
    layout.push = entries[len(entries)//2][0], -1, -3
    layout.record_group(before, layout.push, 0)
    return layout.pack(plan)

"""三排实心输出与六格厚的侧向供电扇出。"""

from .config import MATERIALS
from .layout import Layout


def build_three_rows(plan):
    layout = Layout()
    left, entries = 0, []
    for i, width in enumerate(plan['widths']):
        before = set(layout.blocks)
        material = MATERIALS[(i+plan.get('material_phase', 0)) % 2]
        for x in range(left, left+width):
            layout.put(x, 0, -2, material)
            layout.put(x, 0, -1, 'observer')
            layout.put(x, 0, 0, material)
            for y, z in ((-1, 0), (0, 1), (1, 0)):
                layout.output(x, y, z, 1)
        anchor = left+plan['anchors'][i], 0, -2
        layout.record_group(before, anchor, 1)
        entries.append(anchor)
        left += width
    before = set(layout.blocks)
    for x in range(min(p[0] for p in entries), max(p[0] for p in entries)+1):
        layout.put(x, 1, -4, MATERIALS[plan.get('material_phase', 0)])
    for x, _, _ in entries:
        layout.put(x, 2, -4, 'observer', 'negative_y')
        layout.put(x, 0, -4, 'piston')
    layout.push = entries[len(entries)//2][0], 1, -4
    layout.record_group(before, layout.push, 0)
    return layout.pack(plan)

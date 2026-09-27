"""保留随机生成的同推核心，回退搜索后层回拉与前层延迟输出的连接。"""

from .geometry import add
from .power import sockets


def attach(search, child):
    layout, rng = search.layout, search.rng
    saved = layout.checkpoint()
    candidates = []
    for operation in layout.operations:
        if operation.get('layer') != 0:
            continue
        available = sockets(layout.blocks, operation['added'])
        for p, kinds in available.items():
            entry = add(p, (0, 0, -1))
            if 'pull' in kinds and p[2] == 1 and layout.free(p) and layout.free(entry):
                candidates.append((p, entry, operation['tick']))
    rng.shuffle(candidates)
    for driver, entry, tick in candidates:
        layout.restore(saved)
        if not layout.put(driver, 'sticky_piston', 'negative_z'):
            continue
        layout.links.append(dict(kind='pull', driver=driver, entry=entry, tick=tick))
        if search.extend(child, entry, tick+8):
            return True
    layout.restore(saved)
    return False

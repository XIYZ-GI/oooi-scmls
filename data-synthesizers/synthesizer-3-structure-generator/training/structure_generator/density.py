"""保留现有需求，使用供电空位追加输出并紧凑化目标分布。"""

from .geometry import add
from .power import sockets


def fill(search):
    layout, rng = search.layout, search.rng
    candidates = []
    for operation in layout.operations:
        observers = [p for p in operation['added'] if p in layout.blocks]
        anchor = operation['anchor']
        tick = operation.get('tick')
        if tick is None or (search.category != '推拉结合多时序' and
                            tick+4 not in {v['tick'] for v in layout.outputs}):
            continue
        for p, kinds in sockets(layout.blocks, observers).items():
            if 'push' not in kinds or not layout.free(p):
                continue
            if any(p[:2] == v['piston'][:2] for v in layout.outputs):
                continue
            if any(q[:2] == p[:2] and q[2] > p[2] for q in layout.blocks):
                continue
            candidates.append((p,tick+4,anchor))
    rng.shuffle(candidates)
    # 优先填入现有截面空位，不为提高目标数量任意拉大包围框。
    xs = [p[0] for p in layout.blocks]
    ys = [p[1] for p in layout.blocks]
    candidates.sort(key=lambda v: (max(max(xs),v[0][0])-min(min(xs),v[0][0])+1)*
                    (max(max(ys),v[0][1])-min(min(ys),v[0][1])+1))
    added = 0
    for p,tick,anchor in candidates:
        if len(layout.outputs) >= 32:
            break
        if not layout.free(p) or any(p[:2] == v['piston'][:2] for v in layout.outputs):
            continue
        saved = layout.checkpoint()
        layout.put(p,'piston','positive_z')
        layout.outputs.append(dict(piston=p,tick=tick))
        if search.valid():
            added += 1
        else:
            layout.restore(saved)
    return added

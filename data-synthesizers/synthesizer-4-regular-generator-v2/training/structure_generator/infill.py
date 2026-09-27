"""为尚未供电的入口材料增加有输出用途的侧向观察者。"""

from .config import FACING, MATERIALS, SIDES
from .geometry import add
from .power import sockets
from .front_output import allowed as output_allowed


def grow(search):
    layout, rng = search.layout, search.rng
    candidates = []
    for index, edit in enumerate(layout.operations):
        tick = edit.get('tick',0)+4
        if search.category != '推拉结合多时序' and tick not in {v['tick'] for v in layout.outputs}:
            continue
        for p in edit['added']:
            if layout.blocks.get(p,{}).get('kind') in MATERIALS and p not in edit['charges']:
                for d in SIDES:
                    observer = add(p,d)
                    if layout.free(observer):
                        candidates.append((index,observer,FACING[tuple(-v for v in d)],tick))
    rng.shuffle(candidates)
    count = 0
    for index,observer,facing,tick in candidates[:12]:
        if not layout.free(observer) or len(layout.outputs) >= 32:
            continue
        saved = layout.checkpoint()
        layout.put(observer,'observer',facing)
        options = [p for p,kinds in sockets(layout.blocks,[observer]).items() if 'push' in kinds
                   and output_allowed(layout, p)
                   and layout.free(p) and p[:2] not in {v['piston'][:2] for v in layout.outputs}
                   and not any(q[:2] == p[:2] and q[2] > p[2] for q in layout.blocks)]
        rng.shuffle(options)
        accepted = False
        observed = layout.checkpoint()
        for p in options[:4]:
            layout.restore(observed)
            layout.put(p,'piston','positive_z')
            layout.outputs.append(dict(piston=p,tick=tick))
            if search.valid():
                layout.operations[index]['added'].append(observer)
                accepted = True
                count += 1
                break
        if not accepted:
            layout.restore(saved)
    return count

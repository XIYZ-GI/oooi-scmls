"""逐列搜索动态供电可用的输出空位，预先声明刻数后再验证整机。"""

from ..regular_generator_v2.rectangles import rectangles
from .front_output import allowed as output_allowed


def fill(search):
    layout, rng = search.layout, search.rng
    initial = len(layout.outputs)
    xs, ys = zip(*(p[:2] for p in layout.blocks))
    columns = [(x, y) for x in range(min(xs), max(xs)+1) for y in range(min(ys), max(ys)+1)]
    failed = set()
    while len(layout.outputs) < 32:
        groups = {}
        for output in layout.outputs:
            groups.setdefault(output['tick'], set()).add(output['piston'][:2])
        used = set().union(*groups.values()) if groups else set()
        ticks = sorted({operation['tick']+4 for operation in layout.operations})
        candidates = []
        for x, y in columns:
            if (x, y) in used:
                continue
            front = max((p[2] for p in layout.blocks if p[:2] == (x, y)), default=layout.low-1)
            for z in range(front+1, layout.high+1):
                p = (x, y, z)
                if not layout.free(p) or not output_allowed(layout, p):
                    continue
                for tick in ticks:
                    if (p, tick) in failed:
                        continue
                    region = rectangles(groups.get(tick, set()) | {(x, y)})
                    area = region[0]['area'] if region else 0
                    neighbors = sum((x+dx, y+dy) in used for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))
                    candidates.append((area, neighbors, p, tick))
        rng.shuffle(candidates)
        candidates.sort(key=lambda v: (-v[0], -v[1]))
        accepted = False
        for _, _, p, tick in candidates:
            if search.simulations >= search.options.get('simulation_budget', 48):
                return len(layout.outputs)-initial
            saved = layout.checkpoint()
            if not layout.put(p, 'piston'):
                continue
            layout.outputs.append(dict(piston=p, tick=tick))
            if search.valid():
                accepted = True
                failed.clear()
                break
            layout.restore(saved)
            failed.add((p, tick))
        if not accepted:
            break
    return len(layout.outputs)-initial

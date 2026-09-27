"""用目标占位与接口支持预先化简已有候选，不引入新结构或连接规则。"""

from collections import defaultdict

from .modules import xyz
from .signals import output_power


def reduce_candidates(task, nodes):
    targets = {(t['x'],t['y'],t['z']-2):i for i,t in enumerate(task['targets'])}
    nodes = [n for n in nodes if all(targets[p] in n['covered']
             for p in (xyz(b['position']) for b in n['blocks']) if p in targets)]
    cells = {p:i for i,p in enumerate(sorted({xyz(b['position']) for n in nodes for b in n['blocks']}))}
    masks, outputs, orders, roots = [], [], [], []
    at, parents = defaultdict(list), defaultdict(list)
    for i,n in enumerate(nodes):
        p = xyz(n['anchor'])
        occupied = {xyz(b['position']) for b in n['blocks']}
        masks.append(sum(1<<cells[q] for q in occupied))
        outputs.append(sum(1<<j for j in n['covered']))
        power = output_power(n['blocks'])
        orders.append({task['targets'][j]['order'] for q,j in targets.items() if j in n['covered'] and q in power})
        roots.append(bool(n['covered'] or n['children']) and not any(
            q[:2]==p[:2] and q[2]<p[2] for q in occupied|targets.keys()))
        at[p].append(i)
        for c in n['children']:
            parents[xyz(c['anchor'])].append(i)

    def compatible(parent,child):
        return (not (masks[parent]&masks[child] or outputs[parent]&outputs[child])
                and (not orders[parent] or not orders[child] or max(orders[parent])<min(orders[child])))

    active = set(range(len(nodes)))
    while True:
        rejected = set()
        for i in sorted(active):
            n = nodes[i]
            if any(not any(j in active and compatible(i,j) for j in at[xyz(c['anchor'])]) for c in n['children']):
                rejected.add(i)
            elif not roots[i] and not any(j in active and compatible(j,i) for j in parents[xyz(n['anchor'])]):
                rejected.add(i)
        if not rejected:
            break
        active -= rejected
    return [n for i,n in enumerate(nodes) if i in active]

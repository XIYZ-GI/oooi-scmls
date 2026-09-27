"""对求出的连接图检查运行时运动边界，将错误牵连反馈成可复用约束。"""

from itertools import combinations

from .modules import xyz
from .transport import transport_valid


def moving_nodes(nodes, selected, stamps):
    parents = {}
    for i in selected:
        for c in nodes[i]['children']:
            parents[xyz(c['anchor'])] = (i, xyz(c['driver']))
    moving = {}
    for i in selected:
        node = nodes[i];p = xyz(node['anchor'])
        parent, driver = parents.get(p, (None, (p[0],p[1],p[2]-1)))
        moving[i] = dict(**node, tick=stamps[p], parent=parent, driver=driver)
    return moving


def add_conflicts(model, choose, clock, nodes, selected, stamps):
    moving = moving_nodes(nodes, selected, stamps)
    conflicts = 0
    for i,j in combinations(selected,2):
        a,b = moving[i],moving[j]
        if transport_valid([a,b]):
            continue
        guard = {i,j}
        guard.update(n['parent'] for n in (a,b) if n['parent'] is not None)
        ti,tj = clock[xyz(a['anchor'])],clock[xyz(b['anchor'])]
        if a['tick'] < b['tick']:
            alternative = ti >= tj
        elif a['tick'] > b['tick']:
            alternative = ti <= tj
        else:
            alternative = ti != tj
        model.add(alternative).only_enforce_if([choose[k] for k in sorted(guard)])
        conflicts += 1
    return conflicts

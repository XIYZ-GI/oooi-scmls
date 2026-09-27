"""按格子表达跨单元运动占位和黏附边界，提前排除整体不能移动的装配。"""

from collections import defaultdict

from .modules import xyz


def constrain_space(model, choose, clock, nodes):
    cells = defaultdict(list)
    for i,n in enumerate(nodes):
        for b in n['blocks']:
            cells[xyz(b['position'])].append((i,b['block']['kind'],xyz(n['anchor'])))
    state = {}
    for p,entries in cells.items():
        occupied = model.new_bool_var(f'o{p}')
        model.add(occupied == sum(choose[i] for i,_,_ in entries))
        tick = model.new_int_var(0,96,f'cellt{p}')
        by_anchor = defaultdict(list)
        for i,_,anchor in entries:
            by_anchor[anchor].append(i)
        for anchor,indices in by_anchor.items():
            present = model.new_bool_var(f'a{p}{anchor}')
            model.add(present == sum(choose[i] for i in indices))
            model.add(tick == clock[anchor]).only_enforce_if(present)
        kinds = {}
        for kind in ('slime_block','honey_block','light_blue_glazed_terracotta'):
            flag = model.new_bool_var(f'{kind}{p}')
            model.add(flag == sum(choose[i] for i,k,_ in entries if k==kind))
            kinds[kind] = flag
        state[p] = dict(occupied=occupied,indices={i for i,_,_ in entries},tick=tick,kinds=kinds)
    same = {}

    def different(p,q):
        key = tuple(sorted((p,q)))
        if key not in same:
            eq = model.new_bool_var(f'equal{key}')
            common = state[p]['indices'] & state[q]['indices']
            # 每格至多一个单元；共同占据两格的候选之和即为同属单元标志。
            model.add(eq == sum(choose[i] for i in sorted(common)))
            same[key] = eq
        return same[key].Not()

    for p,a in state.items():
        front = (p[0],p[1],p[2]+1)
        if front in state:
            b = state[front]
            model.add(b['tick']+2 <= a['tick']).only_enforce_if(
                [a['occupied'],b['occupied'],different(p,front)])
            for glue,opposite in (('slime_block','honey_block'),('honey_block','slime_block')):
                model.add(different(p,front) == 0).only_enforce_if(
                    [b['kinds'][glue],a['occupied'],a['kinds'][opposite].Not(),
                     a['kinds']['light_blue_glazed_terracotta'].Not()])
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            for dz in (0,-1):
                q = (p[0]+dx,p[1]+dy,p[2]+dz)
                if q not in state:
                    continue
                b = state[q]
                for glue,opposite in (('slime_block','honey_block'),('honey_block','slime_block')):
                    guard = [a['kinds'][glue],b['occupied'],b['kinds'][opposite].Not(),
                             b['kinds']['light_blue_glazed_terracotta'].Not(),different(p,q)]
                    relation = b['tick'] <= a['tick'] if dz==0 else b['tick'] >= a['tick']
                    model.add(relation).only_enforce_if(guard)
                    if dz==0:
                        model.add(different(p,q) == 0).only_enforce_if([a['kinds'][glue],b['kinds'][glue]])

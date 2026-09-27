"""面向密集目标的逐分支生长与连续两轮物理回退。"""

from collections import Counter

from .preflight import check
from ..domain_rules import proposal_issues
from .construction import connected
from .geometry import add, position
from .growth import supply
from .layout import Layout
from .packing import pack
from .power import sockets
from .planning import plan
from .search_bounds import period_if_in_bounds, completion_issue


class Search:
    def __init__(self, rng, category, depth, dense, options):
        self.rng, self.category, self.depth, self.dense = rng, category, depth, dense
        self.options = options
        self.edits, self.simulations = 0, 0
        self.failures = Counter()
        low = -1 if depth == 3 and category != '多目标同推' else 0
        self.layout = Layout(low, low+depth-1)
        self.layout.reserve_outputs = True

    def valid(self):
        if self.simulations >= self.options.get('simulation_budget', 48):
            return False
        period = period_if_in_bounds(self.layout)
        if period is None:
            return False
        self.simulations += 1
        accepted, reason = check(self.layout, period)
        if not accepted:
            self.failures[reason] += 1
        return accepted

    def extend(self, request, anchor, tick, root=False):
        layout, rng = self.layout, self.rng
        checkpoint = layout.checkpoint()
        for _ in range(20):
            if self.edits >= 180 or self.simulations >= self.options.get('simulation_budget', 48):
                break
            self.edits += 1
            layout.restore(checkpoint)
            pulls = any(k == 'pull' for k, _ in request['children'])
            styles = ['共享供电片', '前置供电']
            if pulls:
                styles = ['入口延伸']*4+styles
            style = '入口延伸' if request.get('extension') else rng.choice(styles)
            added = supply(layout, rng, anchor, style, budget=8, compact=self.dense and not root)
            if not added:
                continue
            layout.operations[-1]['tick'] = tick
            available = sockets(layout.blocks, added)
            links, used = [], set()
            for kind, child in request['children']:
                options = [p for p, kinds in available.items() if kind in kinds and p not in used
                           and layout.free(p) and layout.free(add(p, (0, 0, -1 if kind == 'pull' else 2)))]
                if kind == 'pull' and request.get('extension'):
                    charge = layout.operations[-1]['charges'][-1]
                    options = [p for p in options if sum(abs(a-b) for a,b in zip(p,charge)) == 1]
                if kind == 'pull' and 'pull_offset' in request:
                    options = [p for p in options if p[2] == anchor[2]+request['pull_offset']]
                rng.shuffle(options)
                if kind == 'push' and used:
                    options.sort(key=lambda p: -min(abs(p[0]-q[0])+abs(p[1]-q[1]) for q in used))
                if kind == 'pull':
                    preferred = 1 if self.depth == 2 else anchor[2]+rng.choice((0, 1))
                    if style == '入口延伸':
                        charge = layout.operations[-1]['charges'][-1]
                        options.sort(key=lambda p: sum(abs(a-b) for a,b in zip(p,charge)))
                    else:
                        options.sort(key=lambda p: abs(p[2]-preferred))
                if request.get('heading'):
                    heading = request['heading']
                    options.sort(key=lambda p:-sum((p[i]-anchor[i])*heading[i] for i in (0,1)))
                elif request.get('spread') and used:
                    options.sort(key=lambda p:-min(abs(p[0]-q[0])+abs(p[1]-q[1]) for q in used))
                if not options:
                    break
                p = options[0]
                layout.put(p, 'sticky_piston' if kind == 'pull' else 'piston',
                           'negative_z' if kind == 'pull' else 'positive_z')
                added.add(p)
                used.add(p)
                entry = add(p, (0, 0, -1 if kind == 'pull' else 2))
                links.append((kind, child, p, entry))
            if len(links) != len(request['children']):
                continue
            output_columns = {v['piston'][:2] for v in layout.outputs}
            column_front = {}
            for q in layout.blocks:
                column_front[q[:2]] = max(q[2], column_front.get(q[:2], q[2]))
            outputs = [p for p, kinds in available.items() if 'push' in kinds and p not in used
                       and layout.free(p) and p[:2] not in output_columns
                       and column_front.get(p[:2],p[2]) <= p[2]]
            rng.shuffle(outputs)
            low, high = request['outputs']
            high = min(high, len(outputs), 12-len(added))
            if high < low:
                continue
            count = high if self.dense or rng.random() < .7 else rng.randint(low,high)
            selected = []
            for p in outputs:
                if len(selected) >= count:
                    break
                if p[:2] in {q[:2] for q in selected}:
                    continue
                layout.put(p, 'piston', 'positive_z')
                added.add(p)
                selected.append(p)
                layout.outputs.append(dict(piston=p, tick=tick+4))
            if len(selected) < low or not connected({p: layout.blocks[p] for p in added},anchor):
                continue
            if proposal_issues(dict(blocks=layout.payload(), push=position((0,0,0)))):
                continue
            if not self.valid():
                continue
            success = True
            for kind, child, driver, entry in links:
                layout.links.append(dict(kind=kind,driver=driver,entry=entry))
                if not self.extend(child,entry,tick+(8 if kind=='pull' else 4)):
                    success = False
                    break
            if success:
                return True
        layout.restore(checkpoint)
        return False


def construct(rng, category, depth, dense=False, options=None):
    options = options or {}
    search = Search(rng,category,depth,dense,options)
    request = plan(rng,category,depth,dense,options)
    if not search.extend(request,(0,0,0),4,root=True):
        return None, '分支物理搜索预算用尽'
    layout = search.layout
    if options.get('prune_completion', True):
        reason = completion_issue(layout, options, dense)
        if reason:
            return None, reason
    from .density import fill
    extra = fill(search) if dense else 0
    if dense:
        from .infill import grow
        grown = grow(search)
        extra += grown
        if depth in (2,3) and grown:
            extra += fill(search)
    if len(layout.outputs) < 3 or len(layout.outputs) > 32:
        return None, '输出数量不在三至三十二范围内'
    if max(p[2] for p in layout.blocks)-min(p[2] for p in layout.blocks)+1 != depth:
        return None, '实际厚度未达到请求值'
    row = pack(layout,category,depth,steps=search.edits)
    if row is None:
        return None, '超出空间预算'
    row['construction']['search'] = dict(simulations=search.simulations,failures=dict(search.failures),additional_outputs=extra)
    return row, ''

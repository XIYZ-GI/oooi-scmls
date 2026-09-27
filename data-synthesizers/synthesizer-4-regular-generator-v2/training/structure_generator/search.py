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
from .front_output import allowed as output_allowed


class Search:
    def __init__(self, rng, category, depth, dense, options):
        self.rng, self.category, self.depth, self.dense = rng, category, depth, dense
        self.options = options
        self.edits, self.simulations = 0, 0
        self.failures = Counter()
        low = -1 if depth == 3 and category != '多目标同推' else 0
        self.layout = Layout(low, low+depth-1)
        if options.get('regular'):
            from .regular_policy import RegularLayout
            width, height = self.rng.choice(options.get('section_sizes',
                ((5, 5), (6, 5), (6, 6), (7, 6), (8, 6), (8, 8))))
            high = options.get('front_layers', depth-1 if options.get('mixed', True) else 1)
            self.layout = RegularLayout(high-depth+1, high, width, height)
            self.layout.large_regions = options.get('large_regions', False)
        self.layout.reserve_outputs = True
        if options.get('front_only') or depth > 4 or (options.get('regular') and options.get('mixed', True)
                         and options.get('layered', True)):
            self.layout.output_low = self.layout.high-1

    def valid(self):
        if any(not output_allowed(self.layout, v['piston']) for v in self.layout.outputs):
            self.failures['后层不能直接输出目标'] += 1
            return False
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

    def extend(self, request, anchor, tick, root=False, defer_validation=False):
        layout, rng = self.layout, self.rng
        checkpoint = layout.checkpoint()
        best, best_score, successes = None, None, 0
        for _ in range(self.options.get('branch_attempts', 20)):
            if self.edits >= self.options.get('edit_budget', 180) or self.simulations >= self.options.get('simulation_budget', 48):
                break
            self.edits += 1
            layout.restore(checkpoint)
            pulls = any(k == 'pull' for k, _ in request['children'])
            styles = ['共享供电片', '前置供电']
            if pulls:
                styles = ['入口延伸']*4+styles
            style = '入口延伸' if request.get('extension') else rng.choice(styles)
            if 'layer' in request:
                from .layered_supply import supply as layered_supply
                added = layered_supply(layout, rng, request, anchor, tick)
            elif root and self.options.get('regular') and self.options.get('mixed', True):
                style = '共享供电片'
                added = supply(layout, rng, anchor, style, budget=8, compact=True)
            elif self.options.get('regular') and self.options.get('supply_trials', 1) > 1:
                from .regular_guidance import supply as guided_supply
                added = guided_supply(layout, rng, anchor, style, compact=self.dense and not root,
                                      trials=self.options['supply_trials'])
            elif self.options.get('regular') and rng.random() < .65:
                from .side_growth import supply as side_supply
                added = side_supply(layout, rng, anchor, budget=8)
            else:
                added = supply(layout, rng, anchor, style, budget=8, compact=self.dense and not root)
            if not added:
                continue
            if not added <= layout.blocks.keys():
                continue
            layout.operations[-1]['tick'] = tick
            if 'layer' in request:
                layout.operations[-1]['layer'] = request['layer']
            available = sockets(layout.blocks, added)
            reserved = (set(layout.operations[-1].get('preferred_outputs', []))
                        if request.get('dense_strip') or request.get('solid_strip') else set())
            links, used = [], set()
            for kind, child in request['children']:
                options = [p for p, kinds in available.items() if kind in kinds and p not in used
                           and p not in reserved
                           and layout.free(p) and layout.free(add(p, (0, 0, -1 if kind == 'pull' else 2)))]
                if kind == 'pull' and request.get('extension') and 'layer' not in request:
                    charge = layout.operations[-1]['charges'][-1]
                    options = [p for p in options if sum(abs(a-b) for a,b in zip(p,charge)) == 1]
                if kind == 'pull' and 'pull_offset' in request:
                    options = [p for p in options if p[2] == anchor[2]+request['pull_offset']]
                if kind == 'push' and 'push_offset' in request:
                    options = [p for p in options if p[2] == anchor[2]+request['push_offset']]
                rng.shuffle(options)
                if kind == 'push' and self.options.get('regular') and self.options.get('mixed', True):
                    options.sort(key=lambda p: abs(p[2]-anchor[2]))
                if kind == 'push' and used:
                    if 'layer' not in request or rng.random() < .4:
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
                preferred_pushes = layout.operations[-1].get('preferred_pushes', [])
                if kind == 'push' and preferred_pushes:
                    options.sort(key=lambda p: p not in preferred_pushes)
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
                       and output_allowed(layout, p)
                       and layout.free(p) and p[:2] not in output_columns
                       and column_front.get(p[:2],p[2]) <= p[2]]
            rng.shuffle(outputs)
            if 'layer' in request:
                outputs = [p for p in outputs if request['layer'] <= p[2] <= request['layer']+1]
            if self.options.get('regular'):
                from .regular_policy import prioritize
                prioritize(outputs, layout, tick=tick+4 if 'layer' in request else None)
            preferred = layout.operations[-1].get('preferred_outputs', [])
            if preferred:
                outputs.sort(key=lambda p: p not in preferred)
            low, high = request['outputs']
            if preferred:
                low = max(low, len(preferred))
                high = max(high, low)
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
                if not layout.put(p, 'piston', 'positive_z'):
                    continue
                added.add(p)
                selected.append(p)
                layout.outputs.append(dict(piston=p, tick=tick+4))
            if (len(selected) < low or not reserved <= set(selected)
                    or not connected({p: layout.blocks[p] for p in added},anchor)):
                continue
            if self.depth > 4 and 'layer' in request:
                # 交错分层保留驱动所属运动组，不能单凭重叠的纵深窗口计数。
                layout.operations[-1]['added'] = sorted(added)
            if proposal_issues(dict(blocks=layout.payload(), push=position((0,0,0)))):
                continue
            if not defer_validation and not self.valid():
                continue
            success = True
            if root and self.options.get('atomic_branches') and not defer_validation:
                from .layered_wave import extend_wave
                success = extend_wave(self, links, tick, self.options.get('wave_attempts', 12))
            else:
                for kind, child, driver, entry in links:
                    layout.links.append(dict(kind=kind,driver=driver,entry=entry))
                    if self.options.get('regular'):
                        layout.links[-1]['tick'] = tick
                    if not self.extend(child,entry,tick+(8 if kind=='pull' else 4),
                                       defer_validation=defer_validation):
                        success = False
                        break
            if success:
                if 'layer' in request and self.options.get('branch_variants', 1) > 1:
                    from .layered_score import score
                    quality = score(layout, self.options.get('solid_timing', 'either'))
                    if best_score is None or quality > best_score:
                        best, best_score = layout.checkpoint(), quality
                    successes += 1
                    if successes < self.options['branch_variants']:
                        continue
                    layout.restore(best)
                return True
        if best is not None:
            layout.restore(best)
            return True
        layout.restore(checkpoint)
        return False


def construct(rng, category, depth, dense=False, options=None):
    options = dict(options or {})
    if depth > 4:
        options.update(depth=depth, front_layers=depth-1)
        options.setdefault('edit_budget', 4800)
        options.setdefault('branch_attempts', 60)
    search = Search(rng,category,depth,dense,options)
    request = plan(rng,category,depth,dense,options)
    if options.get('regular'):
        from .regular_policy import request as regular_request
        request = regular_request(rng, category, options)
    if (options.get('feedback_seed') and depth <= 4
            and getattr(search.layout, 'output_low', None) is None):
        request = dict(outputs=(1, 3) if category == '推拉结合多时序' else (0, 0), children=[])
    if not search.extend(request,(0,0,0),4,root=True):
        return None, '分支物理搜索预算用尽'
    if 'staged_rear' in request:
        from .layered_attachment import attach
        if not attach(search, request['staged_rear']):
            return None, '同推核心后的分层回拉连接未完成'
    layout = search.layout
    feedback = []
    if options.get('feedback_growth'):
        from .feedback_growth import grow as grow_feedback, KINDS
        feedback = grow_feedback(search, options.get('feedback_kinds', KINDS),
                                 options.get('feedback_attempts', 80),
                                 options.get('feedback_maximum', 2))
        if len(feedback) < options.get('feedback_minimum', 0):
            return None, '跨组供电或半动机闭环未完成'
        if options.get('feedback_continuation', 0):
            from .feedback_continuation import grow as continue_feedback
            continue_feedback(search, options['feedback_continuation'])
    layered_extra = 0
    if options.get('layered_fill'):
        from .layered_fill import grow as fill_layers
        layered_extra = fill_layers(search)
    if options.get('prune_completion', True) and not (options.get('regular') and options.get('completion_rounds')):
        reason = completion_issue(layout, options, dense)
        if reason:
            return None, reason
    from .density import fill
    extra = layered_extra+(fill(search) if dense else 0)
    if dense:
        from .infill import grow
        grown = grow(search)
        extra += grown
        if depth in (2,3) and grown:
            extra += fill(search)
    if options.get('regular') and options.get('completion_rounds', 0):
        from .regular_completion import complete
        extra += complete(search, options['completion_rounds'])
    if options.get('dynamic_outputs'):
        from .layered_output_search import fill as dynamic_fill
        extra += dynamic_fill(search)
    if len(layout.outputs) < 3 or len(layout.outputs) > 32:
        return None, '输出数量不在三至三十二范围内'
    if max(p[2] for p in layout.blocks)-min(p[2] for p in layout.blocks)+1 != depth:
        return None, '实际厚度未达到请求值'
    row = pack(layout,category,depth,steps=search.edits)
    if row is None:
        return None, '超出空间预算'
    row['construction']['search'] = dict(simulations=search.simulations,failures=dict(search.failures),additional_outputs=extra)
    if options.get('feedback_growth'):
        row['construction']['feedback_growth'] = feedback
    if 'layer' in request:
        from .layer_scheme import describe
        row['construction']['layer_scheme'] = describe(depth, row['proposal']['push']['z'])
    if getattr(layout, 'output_low', None) is not None:
        from .front_output import inspect as inspect_front
        row['construction']['output_policy'] = 'front_only'
        row['front_output'], reason = inspect_front(row)
        if reason:
            return None, reason
    if options.get('regular'):
        row['construction']['random_request'] = request
        row['construction']['section_budget'] = [layout.width, layout.height]
        row['construction']['growth_policy'] = dict(supply_trials=options.get('supply_trials', 1),
                                                    front_layers=options.get('front_layers', 1),
                                                    completion_rounds=options.get('completion_rounds', 0),
                                                    reserve_branches=options.get('reserve_branches', False))
        row['construction']['growth_options'] = dict(options)
        row['source'] += '-regular-growth'
    return row, ''

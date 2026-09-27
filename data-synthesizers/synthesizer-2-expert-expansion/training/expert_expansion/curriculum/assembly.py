"""使用现有单元和运动规则，随机回退装配有界空间中的完整结构。"""

from copy import deepcopy
from itertools import product

from ...domain_rules import proposal_issues
from ...serialization import digest
from ..composition import normalize
from ..modules import orient, xyz
from ..transport import transport_valid
from .catalog import instantiate
from .config import LIMITS, OPTIONS_PER_NODE, SEARCH_STEPS, size_band, target_band


def variants(library):
    result = []
    seen = set()
    for source in library['modules']:
        if source.get('procedural'):
            continue
        for swap, sx, sy, materials in product((False, True), (-1, 1), (-1, 1), (False, True)):
            module = orient(source, swap, sx, sy, materials)
            key = digest([module['core'], module['outputs'], module.get('slots'), module['ports']])
            if key not in seen:
                seen.add(key)
                result.append(module)
    return result


def assemble(catalog, rng, depth, groups, target_size, target_count):
    max_nodes = rng.randint(max(2, groups), max(5, groups*4+4))
    min_nodes = rng.randint(max(1, groups-1), max(2, groups+1))
    if target_count == '13至32目标' or target_size == '大截面':
        min_nodes = max(3, min_nodes)
    terminal_outputs = groups == 1 and rng.random() < .75
    budget = [SEARCH_STEPS]
    limits = {**LIMITS, 'depth': depth}
    diagnostics = dict(backtracks=0, steps=0, max_partial_nodes=0)
    stop = rng.uniform(.1, .55)
    min_targets, max_targets = {'2至5目标': (2, 5), '6至12目标': (6, 12),
                                '13至32目标': (13, 32)}[target_count]
    max_area = {'小截面': 25, '中截面': 64, '大截面': 512}[target_size]

    def walk(frontier, nodes, targets, topology, occupied):
        diagnostics['max_partial_nodes'] = max(diagnostics['max_partial_nodes'], len(nodes))
        # 已经达到本次目标数量和时序要求时，未使用的后继接口不必继续扩展。
        # 这些接口不是必须放置的方块；保留当前结构交给完整模拟器判定，
        # 可以避免为了耗尽所有接口而把目标数量推过上限。
        if frontier and len(nodes) >= min_nodes and min_targets <= len(targets) <= max_targets:
            available_groups = len({t['order'] for t in targets})
            if available_groups >= groups and (len(targets) == max_targets or rng.random() < .3):
                frontier = []
        if not frontier:
            if len(nodes) < min_nodes or len(targets) < 2:
                return None
            order = {tick: i+1 for i, tick in enumerate(sorted({t['order'] for t in targets}))}
            targets = [{**t, 'order': order[t['order']]} for t in targets]
            row = normalize(deepcopy(list(occupied.values())), targets, dict(x=0, y=0, z=0), limits)
            if row is None:
                return None
            task = row['task']
            if (size_band(task['width'], task['height']) != target_size
                    or target_band(len(task['targets'])) != target_count):
                return None
            row['topology'] = topology
            canonical = catalog.canonical
            def tree(index):
                return [canonical[topology[index]['module']], sorted(
                    [tree(i) for i, n in enumerate(topology) if n['parent'] == index], key=str)]
            row.update(group=digest(tree(0)), source='expert_backtracking_composition_v1',
                       family='expert_composition', id=digest([row['task'], row['proposal']])[:24])
            return row
        if budget[0] <= 0:
            return None
        anchor, parent, tick, driver = frontier[0]
        rest = frontier[1:]
        remaining = max_nodes-len(nodes)-len(rest)
        terminate = rng.random() < stop
        pool = catalog.candidates(rng, remaining, not rest and len(nodes)+1 < min_nodes,
                                  terminate, OPTIONS_PER_NODE)
        columns = {(t['x'], t['y']) for t in targets}
        existing = [b['position'] for b in occupied.values()]
        bounds = [(min(p[a] for p in existing), max(p[a] for p in existing))
                  for a in ('x', 'y', 'z')] if existing else None
        for module in pool:
            if budget[0] <= 0:
                break
            budget[0] -= 1
            diagnostics['steps'] += 1
            options = module.get('slots', module['outputs'])
            capacity = min(12-len(module['core']), len(options), max_targets-len(targets))
            if capacity < 0:
                continue
            lower = capacity//2 if target_count == '13至32目标' else 0
            if not rest and not module['ports']:
                lower = max(lower, min_targets-len(targets), 1)
            if lower > capacity:
                continue
            count = 0 if terminal_outputs and module['ports'] else rng.randint(lower, capacity)
            if not count and not module['ports']:
                continue
            chosen = rng.sample(options, count)
            total = len(targets)+count
            if total > max_targets or (not rest and not module['ports'] and total < min_targets):
                continue
            blocks, out, ports = instantiate(module, anchor, chosen)
            if len(blocks) > 12 or any(xyz(b['position']) in occupied for b in blocks):
                continue
            if any((t['x'], t['y']) in columns for t in out) or len(targets)+len(out) > LIMITS['targets']:
                continue
            points = [b['position'] for b in blocks]
            extents = [(min(p[a] for p in points), max(p[a] for p in points)) for a in ('x', 'y', 'z')]
            if bounds:
                extents = [(min(lo, old_lo), max(hi, old_hi))
                           for (lo, hi), (old_lo, old_hi) in zip(extents, bounds)]
            spans = [hi-lo+1 for lo, hi in extents]
            if spans[2] > depth or max(spans[:2]) > 24 or spans[0]*spans[1]*depth > 512:
                continue
            if spans[0]*spans[1] > max_area:
                continue
            if not rest and not ports and size_band(*spans[:2]) != target_size:
                continue
            if proposal_issues(dict(blocks=[*occupied.values(), *blocks], push=dict(x=0, y=0, z=0))):
                continue
            moving = dict(blocks=blocks, anchor=anchor, parent=parent, tick=tick, driver=driver)
            if not transport_valid([*nodes, moving]):
                continue
            for t in out:
                t['order'] = tick+6
            index = len(nodes)
            children = []
            for port in ports:
                p = port['position']
                children.append(({**p, 'z': p['z']+(-1 if port['kind'] == 'pull' else 2)},
                                 index, tick+(8 if port['kind'] == 'pull' else 4), xyz(p)))
            entry = dict(module=module['id'], parent=parent, anchor=anchor, tick=tick,
                         variant=catalog.signatures[id(module)], outputs=len(out), branches=len(ports))
            row = walk([*rest, *children], [*nodes, moving], [*targets, *out],
                       [*topology, entry], {**occupied, **{xyz(b['position']): b for b in blocks}})
            if row is not None:
                return row
            diagnostics['backtracks'] += 1
        return None

    row = walk([(dict(x=0, y=0, z=0), None, 0, (0, 0, -1))], [], [], [], {})
    if row:
        row['requested_sampling'] = dict(depth=depth, groups=groups, size=target_size, targets=target_count)
    return row, diagnostics

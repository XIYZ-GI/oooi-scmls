"""从真实轨迹确认连接、供电、回拉及其后续输出，不按元件数量贴标签。"""

from collections import defaultdict

from .config import CONDUCTORS, VECTORS
from .geometry import add, point


def inspect(row, evaluation):
    frames = evaluation['trace']
    initial = frames[0]['snapshot']
    by_position = {point(b['position']): b for b in initial['blocks']}
    by_id = {b['id']: b for b in initial['blocks']}
    body = {by_position[point(b['position'])]['id'] for b in row['proposal']['blocks']}
    output_ids = {by_position[(t['x'], t['y'], t['z']-2)]['id'] for t in row['task']['targets']}
    functional = output_ids | {by_position[point(v['driver'])]['id'] for v in row['construction']['links']}
    period, rounds = row['task']['max_ticks'], row['task']['rounds']
    motions, charged, pulsed, activations = {}, set(), set(), defaultdict(list)
    completed = set()
    sources, used_observers = defaultdict(set), set()
    first_power = {}
    for frame in frames:
        snapshot = frame['snapshot']
        for motion in snapshot['motions']:
            members = {b['block_id'] for b in motion['blocks']}
            if not members & body:
                continue
            key = (motion['piston_id'], motion['started_at'])
            motions[key] = motion
        actual = {b['id']: b['position'] for b in snapshot['blocks']}
        for key, motion in motions.items():
            if key in completed or snapshot['tick'] != motion['completes_at']:
                continue
            if all(actual.get(b['block_id']) == b['to'] for b in motion['blocks']):
                completed.add(key)
        if snapshot['tick'] <= period:
            charged.update(b['id'] for b in snapshot['blocks'] if b['id'] in body and b['strongly_powered'])
            pulsed.update(b['id'] for b in snapshot['blocks'] if b['id'] in body
                          and b['kind'] == 'observer' and b['observer_phase']['phase'] == 'pulsing')
            for e in snapshot['events']:
                if e['kind'] == 'piston_extension_completed' and e['block_id'] in body:
                    activations[e['block_id']].append(e['tick'])
            world = {point(b['position']): b for b in snapshot['blocks']}
            for piston in snapshot['blocks']:
                if piston['id'] in functional and piston['powered']:
                    first_power.setdefault(piston['id'], snapshot['tick'])
            for p, observer in world.items():
                if observer['id'] not in pulsed or observer.get('observer_phase', {}).get('phase') != 'pulsing':
                    continue
                q = add(p, VECTORS[observer['facing']])
                direct = world.get(q)
                energized = [(q, p, None)]
                if direct and direct['kind'] in CONDUCTORS and direct['strongly_powered']:
                    energized = [(add(q, d), q, direct['id']) for d in VECTORS.values()]
                for receiver, source, charge_id in energized:
                    piston = world.get(receiver)
                    if not piston or piston['id'] not in functional or not piston['powered']:
                        continue
                    if snapshot['tick'] != first_power[piston['id']]:
                        continue
                    if add(receiver, VECTORS[piston['facing']]) == source:
                        continue
                    used_observers.add(observer['id'])
                    sources[piston['id']].add((observer['id'], charge_id))

    links = []
    for expected in row['construction']['links']:
        driver = by_position[point(expected['driver'])]['id']
        entry = by_position[point(expected['entry'])]['id']
        matching = [(key, m) for key, m in motions.items() if m['piston_id'] == driver
                    and m['kind'] == expected['kind'] and m['direction'] == 'positive_z'
                    and entry in {b['block_id'] for b in m['blocks']} and key in completed]
        cycles = {m['started_at']//period for _, m in matching}
        if cycles != set(range(rounds)) or len(matching) != rounds:
            return None, '预期推拉连接未在每轮真实完成'
        first = min((m for _, m in matching), key=lambda m: m['started_at'])
        members = {b['block_id'] for b in first['blocks']}
        observers = members & pulsed
        if not observers:
            return None, '接续搬运未带动有效观察者'
        links.append(dict(**expected, start=first['started_at'], end=first['completes_at'],
                          blocks=len(members), members=sorted(members),
                          observers=len(observers), rounds=len(matching),
                          entry_charged=entry in charged, powered_at=first_power.get(driver),
                          power_sources=[dict(observer=by_id[o]['position'],
                                              charge=by_id[q]['position'] if q is not None else None)
                                         for o, q in sorted(sources[driver], key=str)]))

    # 沿实际搬运关系追到输出，排除仅搬运无用随组块的回拉。
    for link in links:
        descendants = set(link['members'])
        while True:
            old = len(descendants)
            for other in links:
                driver = by_position[point(other['driver'])]['id']
                if driver in descendants:
                    descendants.update(other['members'])
            if old == len(descendants):
                break
        affected = output_ids & descendants
        active_after = [i for i in affected if any(t >= link['end'] for t in activations[i])]
        if not active_after:
            return None, '推拉连接没有通向有效输出'
        link['dependent_outputs'] = len(active_after)
        link['supply_layouts'] = []
        for source in link['power_sources']:
            for edit in row['construction']['operations']:
                if source['observer'] not in edit['added']:
                    continue
                extension = (edit['kind'] == '入口延伸' and source['charge'] == edit['charges'][-1]
                             and len(edit['charges']) > 1)
                primary_id = by_position.get(point(edit['charges'][0]), {}).get('id')
                same_tick_outputs = sum(primary_id is not None and any(q == primary_id for _, q in sources[i])
                                        and first_power.get(i) == link['powered_at'] for i in output_ids)
                link['supply_layouts'].append(dict(style=edit['kind'], anchor=edit['anchor'],
                    extended_input=extension,
                    primary_outputs=same_tick_outputs,
                    driver_depth_offset=link['driver']['z']-edit['anchor']['z']))
    # 各连接的后代追踪会互相读取成员，全部追踪完成后才能清理临时字段。
    for link in links:
        del link['members']

    first_motions = [m for key, m in motions.items() if m['started_at'] < period and key in completed]
    roots = {b['block_id'] for m in first_motions if m['piston_id'] not in body for b in m['blocks']}
    lateral = {i for i in pulsed if by_id[i]['facing'].endswith(('_x', '_y'))}
    multi = [len(charged & {b['block_id'] for b in m['blocks']}) for m in first_motions]
    shared = [v for v in links if v['entry_charged']]
    return dict(links=links, functional_pulls=sum(v['kind'] == 'pull' for v in links),
                functional_pushes=sum(v['kind'] == 'push' for v in links),
                charged_blocks=len(charged), active_observers=len(pulsed),
                lateral_observers=len(lateral), secondary_observers=len(pulsed-roots),
                secondary_lateral_observers=len(lateral-roots),
                useful_lateral_observers=len(lateral & used_observers),
                secondary_useful_lateral_observers=len((lateral-roots) & used_observers),
                max_charged_per_motion=max(multi, default=0),
                shared_input_charges=len(shared), useful_observers=len(used_observers),
                unused_observers=len(pulsed-used_observers),
                saturated_extension_pulls=sum(v['kind'] == 'pull' and any(
                    s['extended_input'] and s['primary_outputs'] >= 4 for s in v['supply_layouts'])
                    for v in links),
                extended_input_pulls=sum(v['kind'] == 'pull' and any(
                    s['extended_input'] for s in v['supply_layouts']) for v in links)), ''

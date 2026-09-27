"""验证跨组供电与回收环；按三轮实际搬运和跨轮输出依赖确认贡献。"""

from .geometry import point
from .mechanism_audit import analyze, power_sources


def inspect(row, evaluation):
    frames = evaluation['trace']
    initial = {b['id']: b for b in frames[0]['snapshot']['blocks']}
    positions = {point(b['position']): i for i, b in initial.items()}
    body = {positions[point(b['position'])] for b in row['proposal']['blocks']}
    period, rounds = row['task']['max_ticks'], row['task']['rounds']
    try:
        audit = analyze(row, evaluation)
    except ValueError as error:
        if str(error) == '目标没有唯一完整十负载推动记录':
            return None, str(error)
        raise
    if audit['covered_blocks'] != len(body) or not all(audit['translation_each_round']):
        return None, '跨组构造本体没有逐轮完整前进一格'
    motions, completed, sources, powered_at = {}, set(), {}, {}
    functional = {positions[point(link['driver'])] for link in row['construction']['links']}
    output_loads = {positions[(t['x'], t['y'], t['z']-2)]:
                    {positions[(t['x'], t['y'], t['z']+i)] for i in range(10)}
                    for t in row['task']['targets']}
    functional |= output_loads.keys()
    for frame in frames:
        snapshot = frame['snapshot']
        for motion in snapshot['motions']:
            key = (motion['piston_id'], motion['kind'], motion['started_at'])
            motions.setdefault(key, motion)
        actual = {b['id']: b['position'] for b in snapshot['blocks']}
        for key, motion in motions.items():
            if snapshot['tick'] == motion['completes_at'] and all(
                    actual.get(b['block_id']) == b['to'] for b in motion['blocks']):
                completed.add(key)
        if snapshot['tick'] >= period:
            continue
        for block in snapshot['blocks']:
            driver = block['id']
            if driver in functional and block['powered'] and driver not in sources:
                powered_at[driver] = snapshot['tick']
                sources[driver] = power_sources(snapshot, driver, initial, {})
    source_ids = {i: {positions[point(s['source'])] for s in values}
                  for i, values in sources.items()}
    links, link_members = [], []
    for expected in row['construction']['links']:
        driver = positions[point(expected['driver'])]
        entry = positions[point(expected['entry'])]
        matching = [m for key, m in motions.items() if key in completed
                    and m['piston_id'] == driver and m['kind'] == expected['kind']
                    and m['direction'] == 'positive_z'
                    and entry in {b['block_id'] for b in m['blocks']}]
        cycle_counts = [sum(m['started_at']//period == cycle for m in matching)
                        for cycle in range(rounds)]
        if not all(cycle_counts) or len(set(cycle_counts)) != 1:
            return None, '预期跨组连接未在每轮真实完成'
        first = min(matching, key=lambda m: m['started_at'])
        members = {b['block_id'] for b in first['blocks']}
        link_members.append((driver, members))
        links.append(dict(**expected, start=first['started_at'], end=first['completes_at'],
                          blocks=len(members), rounds=rounds, powered_at=powered_at.get(driver),
                          motions_per_round=cycle_counts,
                          power_sources=sources.get(driver, []), supply_layouts=[]))
    for link, (_, members) in zip(links, link_members):
        descendants = set(members)
        while True:
            previous = len(descendants)
            for driver, children in link_members:
                if driver in descendants or source_ids.get(driver, set()) & descendants:
                    descendants |= children
            if previous == len(descendants):
                break
        affected = {driver for driver in output_loads
                    if driver in descendants or source_ids.get(driver, set()) & descendants}
        if not affected:
            return None, '跨组连接没有输出或下一轮复位用途'
        link['dependent_outputs'] = len(affected)
        link['next_round_outputs'] = sum(powered_at.get(driver, period) < link['end']
                                          for driver in affected)
    output_pushes = []
    for driver, loads in output_loads.items():
        matching = [m for key, m in motions.items() if key in completed
                    and m['piston_id'] == driver and m['kind'] == 'push'
                    and m['direction'] == 'positive_z'
                    and loads <= {b['block_id'] for b in m['blocks']}]
        if len(matching) != rounds or {m['started_at']//period for m in matching} != set(range(rounds)):
            return None, '跨组构造输出缺少逐轮十负载运动证据'
        output_pushes.append(dict(driver=initial[driver]['position'], kind='push',
                                  rounds=rounds, dependent_outputs=1))
    observers = {positions[point(s['source'])] for v in sources.values() for s in v
                 if s['source_kind'] == 'observer'}
    redstone = {positions[point(s['source'])] for v in sources.values() for s in v
                if s['source_kind'] == 'redstone_block'} & body
    return dict(links=links, output_pushes=output_pushes,
                functional_pulls=sum(e['kind'] == 'pull' for e in links),
                functional_pushes=sum(e['kind'] == 'push' for e in links),
                active_redstone_sources=len(redstone), useful_observers=len(observers),
                mechanism_audit=audit, saturated_extension_pulls=0, extended_input_pulls=0,
                secondary_useful_lateral_observers=0, max_charged_per_motion=0), ''

"""从完整模拟轨迹分别提取本体搬运、输出时刻和跨组供电关系。"""

from collections import Counter

from .config import CONDUCTORS, VECTORS
from .geometry import add, point


def analyze(row, evaluation):
    frames = evaluation['trace']
    initial = {b['id']: b for b in frames[0]['snapshot']['blocks']}
    positions = {point(b['position']): i for i, b in initial.items()}
    body = {positions[point(b['position'])] for b in row['proposal']['blocks']}
    period = row['task']['max_ticks']
    motions = {}
    for frame in frames:
        snapshot = frame['snapshot']
        if snapshot['tick'] >= period:
            break
        for motion in snapshot['motions']:
            if motion['kind'] not in ('push', 'pull'):
                continue
            key = (motion['piston_id'], motion['kind'], motion['started_at'])
            motions.setdefault(key, motion)
    transport = [m for m in motions.values() if any(b['block_id'] in body for b in m['blocks'])]
    transport.sort(key=lambda m: (m['started_at'], m['piston_id']))
    owner, history = {}, {}
    operations = []
    for index, motion in enumerate(transport):
        members = [b['block_id'] for b in motion['blocks'] if b['block_id'] in body]
        for member in members:
            history.setdefault(member, []).append(index)
        owner.update({i: index for i in members})
        driver = initial[motion['piston_id']]
        operations.append(dict(index=index, kind=motion['kind'], start=motion['started_at'],
                               end=motion['completes_at'], driver=driver['position'],
                               external=motion['piston_id'] not in body,
                               member_ids=members, blocks=len(members),
                               depths=sorted({initial[i]['position']['z'] for i in members}),
                               members=[dict(position=initial[i]['position'], kind=initial[i]['kind'],
                                             facing=initial[i]['facing']) for i in members]))
    for operation, motion in zip(operations, transport):
        operation['parent'] = owner.get(motion['piston_id'])
        driver_id = motion['piston_id']
        powered = next((f['snapshot'] for f in frames
                        if f['snapshot']['tick'] <= motion['started_at']
                        and any(b['id'] == driver_id and b['powered']
                                for b in f['snapshot']['blocks'])), None)
        operation['powered_at'] = powered['tick'] if powered else None
        operation['sources'] = power_sources(powered, driver_id, initial, owner) if powered else []
        parent = operation['parent']
        operation['driver_moved_after_work'] = (parent is not None
                                               and operations[parent]['end'] > operation['end'])
    outputs = []
    for index, target in enumerate(row['task']['targets']):
        loads = {positions[(target['x'], target['y'], target['z']+i)] for i in range(10)}
        matching = [m for m in motions.values() if m['kind'] == 'push'
                    and m['direction'] == 'positive_z'
                    and loads <= {b['block_id'] for b in m['blocks']}]
        if len(matching) != 1:
            raise ValueError('目标没有唯一完整十负载推动记录')
        motion = matching[0]
        driver_id = motion['piston_id']
        moved_by = owner.get(driver_id)
        moved_at = operations[moved_by]['end'] if moved_by is not None else None
        powered = next((f['snapshot'] for f in frames if f['snapshot']['tick'] <= motion['started_at']
                        and any(b['id'] == driver_id and b['powered'] for b in f['snapshot']['blocks'])), None)
        supplies = power_sources(powered, driver_id, initial, owner) if powered else []
        outputs.append(dict(index=index, target=target, driver=initial[driver_id]['position'],
                            moved_by=moved_by, moved_at=moved_at,
                            powered_at=powered['tick'] if powered else None,
                            completed_at=motion['completes_at'], sources=supplies,
                            delayed_after_transport=moved_at is not None and motion['completes_at'] > moved_at+4))
    return dict(body_blocks=len(body), covered_blocks=len(owner), operations=operations,
                repeated_transports=[dict(position=initial[i]['position'], operations=indices)
                                     for i, indices in history.items() if len(indices) > 1],
                transport_counts=dict(Counter(m['kind'] for m in transport)), outputs=outputs,
                group_counts=dict(Counter(t['order'] for t in row['task']['targets'])),
                delayed_outputs=[o for o in outputs if o['delayed_after_transport']],
                translation_each_round=[r['translation'] for r in evaluation['rounds']])


def power_sources(snapshot, driver_id, initial, owner):
    """记录首个通电帧的直接或强充能路径，因果必要性仍由消融另验。"""
    world = {point(b['position']): b for b in snapshot['blocks']}
    driver = next(b for b in snapshot['blocks'] if b['id'] == driver_id)
    receiver = point(driver['position'])
    front = add(receiver, VECTORS[driver['facing']])
    sources = []
    for p, block in world.items():
        charge = None
        if block['kind'] == 'redstone_block':
            available = p != front and sum(abs(a-b) for a, b in zip(p, receiver)) == 1
        elif block['kind'] == 'observer' and (block.get('observer_phase') or {}).get('phase') == 'pulsing':
            q = add(p, VECTORS[block['facing']])
            available = q == receiver and p != front
            energized = world.get(q)
            if (energized and energized['kind'] in CONDUCTORS and energized['strongly_powered']
                    and q != front and sum(abs(a-b) for a, b in zip(q, receiver)) == 1):
                available, charge = True, energized['id']
        else:
            continue
        if available:
            sources.append(dict(source=initial[block['id']]['position'], source_kind=block['kind'],
                                source_group=owner.get(block['id']),
                                charge=initial[charge]['position'] if charge is not None else None))
    return sources

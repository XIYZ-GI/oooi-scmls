"""识别侦测端被直接顶推的布局与真实伸出记录，不改变引擎物理。"""

from .constants import AXES, RULE, VECTORS


def layout_issues(blocks, external=None, distances=(1, 2)):
    placed = {tuple(b['position'][a] for a in AXES): b.get('block', b) for b in blocks}
    pistons = [(position, block, 'internal') for position, block in placed.items()
               if block['kind'] in ('piston', 'sticky_piston')]
    if external is not None:
        pistons.append((tuple(external[a] for a in AXES),
                        {'kind': 'piston', 'facing': 'positive_z'}, 'external'))
    issues = []
    for position, piston, origin in pistons:
        facing = piston.get('facing', 'positive_z')
        direction = VECTORS[facing]
        for distance in distances:
            front = tuple(x+distance*d for x, d in zip(position, direction))
            block = placed.get(front)
            if block is None or block['kind'] == 'air':
                continue
            # 观察者 facing 是输出端；同向活塞从其反侧接触的正是侦测端。
            if block['kind'] == 'observer' and block.get('facing', 'positive_z') == facing:
                issues.append({'rule': RULE, 'piston': dict(zip(AXES, position)),
                               'observer': dict(zip(AXES, front)), 'facing': facing,
                               'origin': origin, 'air_gap': distance-1,
                               'evidence': 'adjacent' if distance == 1 else 'one_air_gap_risk'})
            # 前方已有其他方块时，不把隔着它的观察者算成直接顶推。
            break
    return issues


def proposal_issues(proposal):
    push = proposal.get('push')
    external = {**push, 'z': push['z']-1} if push else None
    return layout_issues(proposal['blocks'], external)


def snapshot_issues(snapshot):
    """只检查实际发生的推出，排除粘性活塞回拉和旁侧黏附带动。"""
    by_id = {b['id']: b for b in snapshot['blocks']}
    issues = []
    direct = None
    for motion in snapshot.get('motions', []):
        if motion['kind'] != 'push':
            continue
        piston = by_id.get(motion['piston_id'])
        if not piston:
            continue
        if direct is None:
            direct = layout_issues(snapshot['blocks'], distances=(1,))
        for issue in direct:
            if issue['piston'] == piston['position']:
                issue.update(evidence='runtime_push', tick=snapshot['tick'])
                issues.append(issue)
    return issues

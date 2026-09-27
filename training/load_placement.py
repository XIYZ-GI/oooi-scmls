"""按打标器约定摆放负载：目标首块在该列最前方方块前两格（中间留一格空气）。"""

from copy import deepcopy

LEAD = 2


def column_fronts(proposal):
    fronts = {}
    for block in proposal['blocks']:
        position = block['position']
        key = (position['x'], position['y'])
        fronts[key] = max(fronts.get(key, position['z']), position['z'])
    return fronts


def align_targets(task, proposal, lead=LEAD):
    """把每个目标摆到该候选结构本列前端之后，需求里的 z 只作为初值保留。"""
    fronts = column_fronts(proposal)
    if not fronts:
        return deepcopy(task)
    aligned = deepcopy(task)
    for target in aligned['targets']:
        front = fronts.get((target['x'], target['y']))
        if front is not None:
            target['z'] = front + lead
    return aligned

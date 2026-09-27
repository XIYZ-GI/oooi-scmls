"""两格、三格的同推扇出与拉驱级联需求，不增加内部离合推驱层。"""


def plan(rng, category, depth, options):
    target = options.get('target_goal',3)
    large = options.get('min_long_side',0) >= 8
    leaf = lambda: dict(outputs=(2,7),children=[])
    if category == '多目标同推':
        if depth == 2:
            return dict(outputs=(4,8),children=[])
        return dict(outputs=(0,0),children=[('push',leaf()) for _ in range(rng.choice((2,3,4)))])
    if category == '推拉结合同推':
        count = 3 if 13 <= target < 17 and not large else (rng.choice((2,3)) if target >= 10 or large else rng.choice((1,2)))
        children = [('pull',leaf()) for _ in range(count)]
        if large or target >= 17:
            # 每条输出支路经过相同次数的回拉，末端仍然同刻到达。
            children = [('pull',dict(outputs=(0,0),children=[('pull',leaf())
                         for _ in range(rng.choice((1,2)))])) for _ in range(count)]
        if not (large or target >= 17):
            for _,child in children:
                child['outputs'] = (min(4,max(3,(target+count-1)//count)),7)
        if count == 1 and not (large or target >= 17):
            children[0][1]['outputs'] = (3,7)
        return dict(outputs=(0,0),children=children,spread=large)
    count = 2 if large else rng.choice((1,2))
    levels = (3 if depth == 2 else 2) if large else (2 if target >= 13 else rng.choice((1,2)))
    axis = rng.choice(((1,0,0),(0,1,0))) if large else None
    turn = large and rng.random() < .5
    def chain(level,heading):
        if not level:
            return leaf()
        following = (-heading[1],heading[0],0) if turn and level > 1 else heading
        return dict(outputs=(1,4) if large else (2,5),
                    children=[('pull',chain(level-1,following))],heading=heading)
    children = [('pull',chain(levels-1,tuple(v*(1 if i else -1) for v in axis) if axis else None))
                for i in range(count)]
    outputs = (2,4) if large else ((3,5) if target >= 13 else (2,5))
    if depth == 2 and not large and target >= 10 and options.get('min_extensions',0):
        outputs = (4,5)
    return dict(outputs=outputs,
                children=children,spread=large)

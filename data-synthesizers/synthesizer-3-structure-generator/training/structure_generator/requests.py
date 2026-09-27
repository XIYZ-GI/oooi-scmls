"""构造请求只描述输出与接力需求，不包含任何预制方块单元。"""


def requirements(rng, category, depth, dense=False):
    leaf = lambda: dict(outputs=(2, 6), children=[])
    if depth == 4:
        count = rng.randint(2 if dense else 1, 4 if dense else 3)
        children = []
        delayed = rng.randrange(count)
        for index in range(count):
            if category == '多目标同推':
                child = leaf()
            elif category == '推拉结合同推':
                child = dict(outputs=(0, 0), children=[('pull', leaf())])
            elif index == delayed or rng.random() < .25:
                child = dict(outputs=(1, 4), children=[('pull', leaf())])
            else:
                child = leaf()
            children.append(('push', child))
        early = category == '推拉结合多时序' and rng.random() < .35
        return dict(outputs=(1, 1) if early else (0, 0), children=children)
    if category == '多目标同推':
        if depth == 3:
            return dict(outputs=(0, 0), children=[('push', leaf()) for _ in range(rng.randint(1, 3))])
        return dict(outputs=(3, 8), children=[])
    root = dict(outputs=(0, 0) if category == '推拉结合同推' else (2, 4),
                children=[('pull', leaf()) for _ in range(rng.choice((1, 1, 2)))])
    if category == '推拉结合多时序' and rng.random() < .25:
        root['children'][0] = ('pull', dict(outputs=(1, 3), children=[('pull', leaf())]))
    return root

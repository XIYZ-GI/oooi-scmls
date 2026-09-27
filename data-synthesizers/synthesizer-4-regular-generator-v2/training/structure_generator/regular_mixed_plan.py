"""随机推拉混合需求：并行同推输出区、回拉延迟支路及早期散点。"""


def request(rng):
    leaf = lambda: dict(outputs=(2, rng.randint(5, 7)), children=[])
    branches = rng.choice((3, 4, 4))
    delayed = rng.randrange(branches)
    children = []
    for index in range(branches):
        child = leaf()
        if index == delayed:
            for _ in range(rng.randint(2, 3)):
                child = dict(outputs=(1, rng.randint(1, 3)), children=[('pull', child)])
        children.append(('push', child))
    return dict(outputs=(1, rng.randint(1, 3)), children=children)

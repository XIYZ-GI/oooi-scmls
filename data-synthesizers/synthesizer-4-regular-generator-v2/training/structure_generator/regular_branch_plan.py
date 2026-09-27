"""为密集同推区与外围分时序点采样拉驱需求，不规定任何方块坐标。"""


def request(rng):
    levels = rng.randint(3, 4)
    fanout = rng.choice((2, 2, 3))
    def chain(level):
        if level == 1:
            children = [('pull', dict(outputs=(3, rng.randint(5, 7)), children=[]))
                        for _ in range(fanout)]
        else:
            children = [('pull', chain(level-1))]
            if level > 2 and rng.random() < .2:
                children.append(('pull', dict(outputs=(1, rng.randint(2, 4)), children=[])))
        return dict(outputs=(1, rng.randint(1, 3)), children=children)
    return chain(levels)

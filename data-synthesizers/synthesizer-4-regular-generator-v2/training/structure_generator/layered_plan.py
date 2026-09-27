"""四格厚的前后双层随机需求：后层推拉接力，前层同推输出与回拉延迟。"""


def request(rng, staged=False):
    def front(delayed=False):
        node = dict(layer=2, outputs=(2, rng.randint(5, 7)), children=[])
        if delayed:
            node.update(outputs=(1, rng.randint(2, 4)), pull_offset=1)
            node['children'] = [('pull', front())]
        return node

    children = [('push', front(i == 0 and not staged)) for i in range(rng.choice((2, 3)))]
    rear = dict(layer=0, outputs=(1, rng.randint(1, 2)),
                children=[('push', front(True))], push_offset=0)
    if staged:
        return dict(layer=0, outputs=(0, 0), children=children, push_offset=0,
                    staged_rear=rear, mixed_supply=True)
    children.append(('pull', dict(layer=0, outputs=(1, rng.randint(2, 4)), children=[])))
    pushes = children[:-1]
    rng.shuffle(pushes)
    children = [*pushes, children[-1]]
    return dict(layer=0, outputs=(0, 0), children=children,
                pull_offset=1, push_offset=0, extension=True)

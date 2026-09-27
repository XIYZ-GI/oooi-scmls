"""先在后层并行回拉，再推向前层同刻输出，保留延迟和回拉支路。"""


def request(rng):
    def front(delayed=False):
        result = dict(layer=2, outputs=(2, 7), children=[])
        if delayed:
            result.update(outputs=(1, 4), pull_offset=1,
                          children=[('pull', front())])
        return result

    branches = []
    for index in range(2):
        children = [('push', front(index == 0 and i == 0))
                    for i in range(rng.choice((2, 2, 3)))]
        rng.shuffle(children)
        branches.append(('pull', dict(layer=0, outputs=(0, 1), push_offset=0,
                                       children=children)))
    return dict(layer=0, outputs=(1, 2), pull_offset=1, children=branches)

"""由实际层间接口采样推拉往返需求，不读取专家坐标或整机配方。"""


def request(rng, dense=False, rectangular=False):
    def leaf(layer, outputs=(1, 5)):
        return dict(layer=layer, outputs=outputs, children=[])

    return_branch = dict(layer=0, outputs=(1, 3), return_supply=True, push_offset=-1,
                         children=[('push', leaf(2, (2, 7)))])
    front_relay = dict(layer=2, outputs=(1, 4), pull_offset=0,
                       children=[('pull', return_branch)])
    # 后层同刻推向前层多个支路，其中一条从前层回拉到后层，再向前接续。
    children = [('push', front_relay)]
    children.extend(('push', leaf(2, (2, 7))) for _ in range(1 if rectangular else rng.choice((1, 2))))
    rng.shuffle(children)
    children.append(('pull', leaf(0, (1, 4))))
    if dense or rectangular:
        for kind, child in children:
            if kind == 'push':
                child['dense_strip'] = True
    return dict(layer=0, outputs=(0, 0), push_offset=0, pull_offset=1,
                extension=True, children=children, rectangular_fan=rectangular)

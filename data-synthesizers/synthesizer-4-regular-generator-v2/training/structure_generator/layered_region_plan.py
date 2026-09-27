"""先组合两片同刻输出区，再接其他时序，避免延迟支路抢占矩形接口。"""


def request(rng, dense=False):
    def front(delayed=False):
        result = dict(layer=2, outputs=(2, 7), children=[])
        if delayed:
            result.update(outputs=(1, 3), pull_offset=0, children=[('pull', dict(
                layer=0, outputs=(1, 3), return_supply=True, push_offset=-1,
                children=[('push', dict(layer=2, outputs=(1, 5), children=[]))]))])
        else:
            result['dense_strip' if dense else 'solid_strip'] = True
        return result

    return dict(layer=0, outputs=(0, 0), push_offset=0, pull_offset=1, extension=True,
                children=[('push', front()), ('push', front()), ('push', front(True)),
                          ('pull', dict(layer=0, outputs=(1, rng.randint(2, 4)), children=[]))])

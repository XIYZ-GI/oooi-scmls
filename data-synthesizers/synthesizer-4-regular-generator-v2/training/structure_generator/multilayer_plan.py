"""后层推拉接力到前层，只有前层声明目标输出。"""

from .layer_scheme import bands


def request(rng, depth, category='推拉结合多时序'):
    final = bands(depth)[-1]['start']
    before = 0 if depth == 4 else 2

    def output():
        return dict(layer=final, outputs=(2, 6), children=[])

    def return_front():
        child = dict(layer=before, outputs=(0, 0), relay_only=True,
                     return_supply=True, push_offset=-1,
                     children=[('push', output())])
        return dict(layer=final, outputs=(1, 4), pull_offset=0,
                    children=[('pull', child)])

    def delivery(delayed=False):
        if depth == 4:
            return return_front() if delayed else output()
        children = [('push', return_front() if delayed else output())]
        if delayed:
            children.append(('pull', dict(layer=2, outputs=(0, 0), relay_only=True,
                push_offset=0, children=[('push', output())])))
        if rng.random() < .35:
            children.insert(0, ('push', output()))
        return dict(layer=2, outputs=(0, 0), relay_only=True,
                    push_offset=0, pull_offset=1, children=children)

    if category == '多目标同推':
        return dict(layer=0, outputs=(0, 0), relay_only=True, push_offset=0,
                    children=[('push', delivery()) for _ in range(rng.choice((1, 2)))])
    rear_return = dict(layer=0, outputs=(0, 0), relay_only=True,
                       push_offset=0, children=[('push', delivery())])
    if category == '推拉结合同推':
        return dict(layer=0, outputs=(0, 0), relay_only=True, pull_offset=1,
                    children=[('pull', rear_return)])
    return dict(layer=0, outputs=(0, 0), relay_only=True,
                push_offset=0, pull_offset=1, mixed_supply=True,
                children=[('push', delivery(True)), ('pull', rear_return)])

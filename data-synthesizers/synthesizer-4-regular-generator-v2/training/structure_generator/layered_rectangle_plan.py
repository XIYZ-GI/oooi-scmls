"""将两个小运动组的完整输出区拼接，后续仍由随机支路生长复杂度。"""


def request(rng, end_observers=None):
    children = [('push', dict(layer=2, outputs=(6, 6), children=[], dense_strip=True))
                for _ in range(2)]
    rng.shuffle(children)
    return dict(layer=0, outputs=(0, 0), children=children,
                rectangular_fan=True, push_offset=0, end_observers=end_observers)

"""中小尺寸批次的需求配额；尺寸和复杂度同时固定，不能以成功率替代覆盖。"""

import random


SIZES = ((5, 5), (6, 5), (7, 5), (6, 6), (8, 6), (8, 8), (10, 8), (10, 10))
POLICY = dict(min_density=.72, max_empty_area=4, max_distance=1,
              min_groups=4, min_simultaneous=11, min_solid_fraction=.4,
              solid_timing='either', simultaneous_scope='any',
              max_depth=6, min_size_kinds=3, min_side=4, max_side=12, max_area=100)


def requests(count, seed=20260924):
    """轮转尺寸配额；返回需求而非可运行结构，失败需求不得静默换成容易尺寸。"""
    if count < len(SIZES):
        raise ValueError('完整合成批次至少需要八条需求，覆盖全部尺寸档位')
    rng = random.Random(seed)
    result = []
    for index in range(count):
        width, height = SIZES[index % len(SIZES)]
        result.append(dict(index=index, width=width, height=height,
                           min_targets=(width*height*72+99)//100,
                           min_groups=rng.choice((4, 5)),
                           topology=('串联分支', '并联分支', '混合分支')[index % 3],
                           **{k: v for k, v in POLICY.items() if k != 'min_groups'}))
    return result

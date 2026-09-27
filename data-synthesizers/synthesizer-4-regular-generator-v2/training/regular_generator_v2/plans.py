"""预先采样完整实心目标带、时序条带和外围散点条件。"""

import random

from .config import COMPACT_PROFILE, COMPOSITE_PROFILES, HYBRID_PROFILE, PROFILES


def sample_plan(seed, index, profile):
    if profile not in PROFILES:
        raise ValueError('未知的规律密集专项')
    rng = random.Random(f'{seed}:{index}:{profile}')
    if profile == COMPACT_PROFILE:
        return dict(profile=profile, mode='compact_pull', root_side=rng.choice((3, 7)),
                    center_outputs=[rng.choice((0, 2)), rng.choice((8, 10)),
                                    rng.choice((0, 2)), rng.choice((8, 10))],
                    material_phase=rng.randrange(2))
    if profile == HYBRID_PROFILE:
        return dict(profile=profile, mode='hybrid_pull', rectangle_width=rng.choice((12, 13, 14)),
                    tail_variant=rng.randrange(2), material_phase=rng.randrange(2))
    if profile in COMPOSITE_PROFILES:
        return dict(profile=profile, mode='pull_composite', branches=2 if profile == COMPOSITE_PROFILES[0] else 4,
                    rectangle_width=rng.choice((12, 13, 14)), tail_variant=rng.randrange(2),
                    material_phase=rng.randrange(2))
    simultaneous = profile.startswith('同时')
    scatter = profile.endswith('散点')
    scatter_count = rng.choice((1, 2)) if scatter else 0
    count = rng.choice((3, 4)) if scatter_count == 2 else (
        rng.choice((2, 3, 4)) if simultaneous else rng.choice((2, 3, 4)))
    widths = ([rng.randint(1, 3) for _ in range(count)] if simultaneous else
              [rng.randint(1, 2), *([2]*(count-2)), rng.randint(1, 3)])
    if scatter:
        widths[0] = 1
    if scatter_count == 2:
        widths[-1] = 1
    if sum(widths) < 4:
        widths[-1] += 4-sum(widths)
    flips = ([rng.choice((False, True)) for _ in widths] if simultaneous else
             [rng.choice((False, True))]*count)
    plan = dict(profile=profile, mode='simultaneous' if simultaneous else 'staged',
                widths=widths, flips=flips, scatter=scatter, scatter_count=scatter_count,
                anchors=[rng.randrange(w) for w in widths],
                spine_y=rng.randrange(2), rear_observers=bool(rng.randrange(2)),
                material_phase=rng.randrange(2))
    if simultaneous and not scatter and rng.random() < .3:
        widths = [rng.randint(1, 2) for _ in range(rng.choice((2, 3)))]
        if sum(widths) < 3:
            widths[-1] = 2
        plan.update(rows=3, widths=widths, anchors=[rng.randrange(w) for w in widths])
    elif simultaneous and rng.random() < .35:
        plan.update(side_root=True, flips=[False]*len(widths))
    elif not simultaneous and rng.random() < .4:
        widths = [rng.randint(1, 2), rng.randint(1, 3), rng.randint(1, 2), rng.randint(1, 3)]
        if scatter:
            widths[0] = 1
        if scatter_count == 2:
            widths[-1] = 1
        plan.update(mode='parallel_staged', widths=widths, flips=[False]*4)
    return plan

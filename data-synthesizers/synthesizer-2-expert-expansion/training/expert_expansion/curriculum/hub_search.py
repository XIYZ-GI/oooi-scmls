"""搜索可运行的并行推驱中心几何：外部活塞推的方块与观察者分离，避免侦测端禁忌。"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import os
from pathlib import Path
import random

from ...evaluator import evaluate
from ...serialization import digest, write_json
from ..composition import normalize
from .parallel import block

AXES = ('x', 'y', 'z')
VECTORS = dict(positive_x=(1, 0, 0), negative_x=(-1, 0, 0), positive_y=(0, 1, 0),
               negative_y=(0, -1, 0), positive_z=(0, 0, 1), negative_z=(0, 0, -1))
MATERIALS = ('slime_block', 'honey_block')


def neighbour_slots(center):
    """强充能方块周围可放活塞的位置，含对角。"""
    x, y, z = center
    slots = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx, dy) == (0, 0):
                continue
            slots.append((x+dx, y+dy, z))
    return slots


def build(design):
    """按设计参数搭建结构，返回需求和方案；空结构返回 None。"""
    push, material, observer, facing, charge, pistons = (design['push'], design['material'],
        design['observer'], design['facing'], design['charge'], design['pistons'])
    core = [block(*push, material), block(*observer, 'observer', facing), block(*charge, material)]
    positions = {tuple(item['position'][a] for a in AXES) for item in core}
    if len(positions) != len(core):
        return None
    piston_blocks = [block(x, y, z, 'piston') for x, y, z in pistons]
    if any(tuple(item['position'][a] for a in AXES) in positions for item in piston_blocks):
        return None
    if len(core)+len(piston_blocks) > 12:
        return None
    targets = [dict(x=item['position']['x'], y=item['position']['y'],
                    z=item['position']['z']+2, order=1) for item in piston_blocks]
    blocks = [*core, *piston_blocks]
    row = normalize(blocks, targets, dict(core[0]['position']),
                    dict(width=32, height=32, depth=6, volume=1024, targets=32))
    if row is None:
        return None
    row['task']['max_ticks'] = 64
    return row, design


def sample(rng, output_range):
    """随机一个或多个并行推驱中心；被推方块与被观察者分离。"""
    hubs = rng.choice((1, 1, 2, 2, 3))
    spacing = rng.randint(2, 3)
    xs = [index*spacing for index in range(hubs)]
    material = rng.choice(MATERIALS)
    core, occupied = [], set()
    for x in xs:
        core.append(block(x, 0, 0, 'observer'))
        core.append(block(x, 0, 1, material))
        occupied.update({(x, 0, 0), (x, 0, 1)})
    for left, right in zip(xs, xs[1:]):
        for x in range(left+1, right):
            core.append(block(x, 0, 1, material))
            occupied.add((x, 0, 1))
    # 外部活塞推的方块必须与观察者分离：放在强充能层或观察者层旁边。
    push_choices = [(xs[0], -1, 1), (xs[0], 1, 1), (xs[-1], -1, 1), (xs[-1], 1, 1),
                    (xs[0], -1, 0), (xs[-1], 1, 0)]
    rng.shuffle(push_choices)
    push = next((item for item in push_choices if item not in occupied), None)
    if push is None:
        return None
    core.append(block(*push, material))
    occupied.add(push)
    slots = [slot for slot in {slot for cell in occupied if cell[2] == 1
                               for slot in neighbour_slots(cell)} if slot not in occupied]
    if len(slots) < 2:
        return None
    rng.shuffle(slots)
    limit = min(len(slots), output_range, 12-len(core))
    count = rng.randint(2, max(2, limit))
    pistons = slots[:count]
    if any(cell[2] != 1 for cell in pistons):
        return None
    return dict(push=push, material=material, observer=(xs[0], 0, 0),
                facing='positive_z', charge=(xs[0], 0, 1), pistons=pistons, hubs=xs)


def attempt(job):
    seed, output_range = job
    rng = random.Random(seed)
    design = sample(rng, output_range)
    if design is None:
        return dict(seed=seed, accepted=False, reason='设计非法')
    built = build(design)
    if built is None:
        return dict(seed=seed, accepted=False, reason='结构非法')
    row, design = built
    value = evaluate(row['task'], row['proposal'], foundation=True)
    return dict(seed=seed, accepted=value['accepted'], reason=value['reason'],
                design=design, task=row['task'], proposal=row['proposal'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempts', type=int, default=4000)
    parser.add_argument('--workers', type=int, default=0)
    parser.add_argument('--output-range', type=int, default=8)
    parser.add_argument('--seed', type=int, default=20260924)
    parser.add_argument('--output', type=Path, default=Path('data/generation/parallel-hub-search'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    workers = args.workers or min(8, max(1, (os.cpu_count() or 2)-1))
    jobs = [(args.seed+i, args.output_range) for i in range(args.attempts)]
    winners, reasons = [], {}
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        for index, result in enumerate(pool.map(attempt, jobs, chunksize=4), 1):
            if result['reason']:
                reasons[result['reason']] = reasons.get(result['reason'], 0) + 1
            if result['accepted']:
                winners.append(result)
            if index % 500 == 0:
                print(json.dumps(dict(attempts=index, winners=len(winners)), ensure_ascii=False), flush=True)
    write_json(args.output/'winners.json', dict(attempts=args.attempts, seed=args.seed,
                                                winners=winners, reasons=reasons))
    shapes = {}
    for row in winners:
        design = row['design']
        key = (design['facing'], len(design['pistons']), design['material'],
               tuple(a-b for a, b in zip(design['observer'], design['push'])))
        shapes[str(key)] = shapes.get(str(key), 0) + 1
    write_json(args.output/'shapes.json', shapes)
    print(json.dumps(dict(attempts=args.attempts, winners=len(winners), reasons=reasons), ensure_ascii=False))


if __name__ == '__main__':
    main()

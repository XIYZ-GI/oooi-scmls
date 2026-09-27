"""按完整机械构造规则制作紧凑示范，不执行随机单块修改。"""

from itertools import combinations

from ..serialization import digest
from ..templates import block, geometry_key


def record(blocks, push, targets, family, group=None, split=None):
    xs = [b["position"]["x"] for b in blocks]+[t["x"] for t in targets]
    ys = [b["position"]["y"] for b in blocks]+[t["y"] for t in targets]
    mx, my = min(xs), min(ys)
    for p in [*[b["position"] for b in blocks], push, *targets]:
        p["x"] -= mx
        p["y"] -= my
    group = group or "strong-"+digest(geometry_key([(p["x"], p["y"], p["z"], p["order"]) for p in targets]))
    if split is None:
        bucket = int(digest(group)[:8], 16) % 10
        split = "test" if bucket < 2 else "validation" if bucket < 4 else "train"
    task = {"width": max(xs)-mx+1, "height": max(ys)-my+1, "depth": 2,
            "targets": targets, "max_ticks": 32, "rounds": 3, "load_blocks": 10}
    return {"task": task, "proposal": {"blocks": blocks, "push": push}, "family": family,
            "group": group, "split": split, "source": "compact_rules_v1"}


def strong_rules():
    for hubs, outputs, push in (
        ([(1, 1)], [(0, 1), (1, 0), (1, 2), (2, 1)], (1, 1)),
        ([(1, 1), (3, 1)], [(0, 1), (1, 0), (1, 2), (2, 1), (3, 0), (3, 2), (4, 1)], (2, 1)),
    ):
        for count in range(2, min(len(outputs), 7)+1):
            for points in combinations(outputs, count):
                blocks = [block(x, y, z, kind) for x, y in hubs
                          for z, kind in ((-3, "observer"), (-2, "slime_block"))]
                if len(hubs) > 1:
                    blocks.append(block(2, 1, -3, "slime_block"))
                blocks += [block(x, y, -2, "piston") for x, y in points]
                targets = [dict(x=x, y=y, z=0, order=1) for x, y in points]
                yield record(blocks, dict(x=push[0], y=push[1], z=-3), targets, "strong_compact")


def pull_rules(source_group):
    # 来自训练成品移动线12的两级机械关系，所有参数后代保持在训练来源。
    first_options = [(0, 1), (2, 1)]
    second_options = [(3, 0), (4, 1), (3, 2)]
    for left_count in range(3):
        for extra in combinations(first_options, left_count):
            first = [(1, 0), *extra]
            for right_count in range(1, 4):
                for second in combinations(second_options, right_count):
                    for material in ("slime_block", "honey_block"):
                        blocks = [block(1, 1, -3, "observer"), block(1, 1, -2, "slime_block"),
                                  block(1, 0, -3, "slime_block"), block(1, 2, -2, "sticky_piston")]
                        blocks[-1]["block"]["facing"] = "negative_z"
                        blocks += [block(x, 2, -3, material) for x in (1, 2, 3)]
                        blocks += [block(3, 1, -3, "observer"), block(3, 1, -2, material)]
                        blocks += [block(x, y, -2, "piston") for x, y in [*first, *second]]
                        targets = [dict(x=x, y=y, z=0, order=order)
                                   for order, points in ((1, first), (2, second)) for x, y in points]
                        yield record(blocks, dict(x=1, y=0, z=-3), targets, "pull_compact", source_group, "train")

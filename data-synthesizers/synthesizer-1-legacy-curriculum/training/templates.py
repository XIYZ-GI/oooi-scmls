"""小任务示范规则：共同搬运的输出列，以及分离负载的两级接力。"""

from itertools import combinations

from .serialization import digest


def block(x, y, z, kind):
    return {"position": {"x": x, "y": y, "z": z}, "block": {"kind": kind, "facing": "positive_z"}}


def geometry_key(points):
    """平移、截面旋转和镜像的后代归到同一来源；每个实际示范另行模拟。"""
    variants = []
    for swap in (False, True):
        for sx in (-1, 1):
            for sy in (-1, 1):
                p = [(sx*(y if swap else x), sy*(x if swap else y), z, order) for x, y, z, order in points]
                mx, my = min(t[0] for t in p), min(t[1] for t in p)
                variants.append(sorted((x-mx, y-my, z, order) for x, y, z, order in p))
    return min(variants)


def bridge(points):
    root = min(points)
    connected = {root}
    for point in sorted(points):
        x, y = root
        while x != point[0]:
            x += 1 if x < point[0] else -1
            connected.add((x, y))
        while y != point[1]:
            y += 1 if y < point[1] else -1
            connected.add((x, y))
    return connected


def simultaneous(points, material):
    rear = bridge(points)
    if len(rear)+2*len(points) > 12:
        return None
    blocks = [block(x, y, -4, material) for x, y in sorted(rear)]
    blocks += [block(x, y, z, kind) for x, y in sorted(points) for z, kind in ((-3, "observer"), (-2, "piston"))]
    return blocks, {"x": min(points)[0], "y": min(points)[1], "z": -4}, [
        {"x": x, "y": y, "z": 0, "order": 1} for x, y in sorted(points)]


def relay(points, material):
    left, right = sorted(points)
    if abs(left[0]-right[0])+abs(left[1]-right[1]) < 2:
        return None
    rear = bridge(points)
    if len(rear)+4 > 12:
        return None
    blocks = [block(x, y, -8, material) for x, y in sorted(rear)]
    blocks += [block(x, y, z, kind) for x, y in (left, right) for z, kind in ((-7, "observer"), (-6, "piston"))]
    blocks += [block(*right, z, kind) for z, kind in ((-4, material), (-3, "observer"), (-2, "piston"))]
    return blocks, {"x": left[0], "y": left[1], "z": -8}, [
        {"x": left[0], "y": left[1], "z": -4, "order": 1},
        {"x": right[0], "y": right[1], "z": 0, "order": 2}]


def candidates(extent=4):
    lattice = [(x, y) for x in range(extent) for y in range(extent)]
    for count in (1, 2, 3):
        for points in combinations(lattice, count):
            if min(x for x, y in points) != 0 or min(y for x, y in points) != 0:
                continue
            for family, constructor in (("parallel", simultaneous), ("relay", relay)):
                if family == "relay" and count != 2:
                    continue
                prototype = constructor(points, "slime_block")
                if prototype is None:
                    continue
                targets = prototype[2]
                group = digest([family, geometry_key([(p["x"], p["y"], p["z"], p["order"]) for p in targets])])
                # 在结果产生前固定来源划分，尺寸、平移、黏附材料均继承同一划分。
                bucket = int(group[:8], 16) % 10
                split = "test" if bucket == 0 else "validation" if bucket == 1 else "train"
                for material in ("slime_block", "honey_block"):
                    built = constructor(points, material)
                    for ox, oy, padding in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)):
                        width = max(x for x, y in points)+1+ox+padding
                        height = max(y for x, y in points)+1+oy+padding
                        blocks = [{**b, "position": {**b["position"], "x": b["position"]["x"]+ox, "y": b["position"]["y"]+oy}} for b in built[0]]
                        push = {**built[1], "x": built[1]["x"]+ox, "y": built[1]["y"]+oy}
                        targets = [{**p, "x": p["x"]+ox, "y": p["y"]+oy} for p in built[2]]
                        task = {"width": width, "height": height, "depth": 3 if family == "parallel" else 7,
                                "targets": targets, "max_ticks": 32, "rounds": 3, "load_blocks": 10}
                        yield {"task": task, "proposal": {"blocks": blocks, "push": push}, "group": group,
                               "family": family, "split": split, "source": "rules_v1"}

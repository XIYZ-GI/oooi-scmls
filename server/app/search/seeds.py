import hashlib

from app.models.label_timing import LabelTimingRequest
from app.repositories.library import encoded, library_repository


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def canonical(blocks):
    """无朝向作用的方块统一方向，仅用于搜索与去重。"""
    return sorted([
        {"position": dict(item["position"]), "block": {
            "kind": item["block"]["kind"],
            "facing": item["block"]["facing"] if item["block"]["kind"] in
            ("piston", "sticky_piston", "observer") else "positive_z",
        }} for item in blocks
    ], key=lambda item: tuple(item["position"][axis] for axis in ("x", "y", "z")))


def signature(seed):
    # 这里只按几何重合归组，不推断红石工作原理。
    return {(b["position"]["x"], b["position"]["y"], b["position"]["z"], b["block"]["kind"])
            for b in seed["request"]["blocks"]}


def freeze_seeds():
    seeds = []
    for sample in library_repository.list("samples"):
        timing = sample.get("timing") or {}
        if timing.get("status") != "success" or sample.get("annotationIssue"):
            continue
        shape = sample["normalized"]
        if any(b["layer"] != 0 or not b["kind"] for b in shape["blocks"]):
            continue
        request = LabelTimingRequest(
            blocks=[{"position": b["position"], "block": {"kind": b["kind"], "facing": b["facing"]}}
                    for b in shape["blocks"]],
            push_point=sample["pushPoint"], targets=sample["targets"], max_ticks=timing["maxTicks"],
        ).model_dump()
        request["blocks"] = canonical(request["blocks"])
        seeds.append({"id": sample["id"], "name": sample["name"], "revision": sample["revision"],
                      "source": sample, "request": request, "reference": timing,
                      "width": shape["width"], "height": shape["height"], "depth": shape["depth"],
                      "hash": digest(request)})
    if not seeds:
        raise ValueError("服务器没有带有效十块负载时序的已标注样本")
    seeds.sort(key=lambda s: s["id"])
    groups = list(range(len(seeds)))
    signatures = [signature(s) for s in seeds]
    for i, left in enumerate(signatures):
        for j in range(i):
            right = signatures[j]
            if len(left & right) / len(left | right) >= 0.65:
                old, new = groups[i], groups[j]
                groups = [new if group == old else group for group in groups]
    unique = sorted(set(groups), key=lambda g: digest(sorted(seeds[i]["id"] for i, v in enumerate(groups) if v == g)))
    for i, seed in enumerate(seeds):
        rank = unique.index(groups[i])
        # 固定整个实验的来源划分，所有后代继承；不按修改记录随机切分。
        holdout = max(1, len(unique) // 5) if len(unique) >= 3 else 0
        seed["split"] = "validation" if rank < holdout else "test" if rank < holdout * 2 else "train"
        seed["group"] = digest(sorted(seeds[k]["id"] for k, g in enumerate(groups) if g == groups[i]))[:16]
    return seeds

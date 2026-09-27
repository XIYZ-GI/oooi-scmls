import copy

from app.models.label_timing import LabelTimingRequest
from .seeds import canonical, digest


KINDS = ["slime_block", "honey_block", "piston", "sticky_piston", "observer", "redstone_block",
         "iron_block", "glass", "light_blue_glazed_terracotta"]
DIRECTIONS = ["positive_x", "negative_x", "positive_y", "negative_y", "positive_z", "negative_z"]
OPERATIONS = ["delete", "move", "rotate", "replace", "add", "compress"]
LABELS = {"delete": "删除方块", "move": "移动一格", "rotate": "改变朝向", "replace": "替换方块", "add": "添加方块", "compress": "压缩一层"}


def metrics(blocks):
    zs = [b["position"]["z"] for b in blocks]
    return max(zs) - min(zs) + 1, len(blocks)


def propose(seed, parent, rng):
    blocks = copy.deepcopy(parent["blocks"])
    push = dict(parent["push"])
    index = rng.randrange(len(blocks))
    selected = blocks[index]
    before = copy.deepcopy(selected)
    operation = rng.choices(OPERATIONS, weights=[3, 3, 2, 4, 1, 2])[0]
    detail = {"operation": operation, "label": LABELS[operation], "before": before}
    if operation == "delete":
        if selected["position"] == push or len(blocks) == 1:
            return None
        blocks.pop(index)
    elif operation == "rotate":
        if selected["block"]["kind"] not in ("piston", "sticky_piston", "observer"):
            return None
        selected["block"]["facing"] = rng.choice([d for d in DIRECTIONS if d != selected["block"]["facing"]])
    elif operation == "replace":
        kind = selected["block"]["kind"]
        choices = {"slime_block": ["honey_block"], "honey_block": ["slime_block"],
                   "piston": ["sticky_piston"], "sticky_piston": ["piston"],
                   "iron_block": ["glass", "light_blue_glazed_terracotta"],
                   "glass": ["iron_block", "light_blue_glazed_terracotta"],
                   "light_blue_glazed_terracotta": ["glass", "iron_block"]}.get(kind, KINDS)
        selected["block"]["kind"] = rng.choice([k for k in choices if k != kind])
    elif operation in ("move", "add"):
        axis = rng.choice(["x", "y", "z"])
        if operation == "add":
            selected = copy.deepcopy(selected)
            selected["block"] = {"kind": rng.choice(KINDS), "facing": rng.choice(DIRECTIONS)}
            blocks.append(selected)
        selected["position"][axis] += rng.choice([-1, 1])
        if operation == "move" and before["position"] == push:
            push = dict(selected["position"])
    else:
        zs = [b["position"]["z"] for b in blocks]
        if min(zs) == max(zs):
            return None
        cut = rng.randint(min(zs), max(zs) - 1)
        for b in blocks:
            if b["position"]["z"] <= cut:
                b["position"]["z"] += 1
        if push["z"] <= cut:
            push["z"] += 1
        detail["cut"] = cut
    detail["after"] = None if operation == "delete" else copy.deepcopy(selected)
    if any(not 0 <= b["position"]["x"] < seed["width"] or not 0 <= b["position"]["y"] < seed["height"]
           or b["position"]["z"] < -seed["depth"] - 1 for b in blocks):
        return None
    # 厚度变化不平移目标、不重新归一化；截面的外包络保持原规格。
    if any(min(b["position"][a] for b in blocks) != 0 or max(b["position"][a] for b in blocks) != size - 1
           for a, size in (("x", seed["width"]), ("y", seed["height"]))):
        return None
    blocks = canonical(blocks)
    try:
        LabelTimingRequest(**{**seed["request"], "blocks": blocks, "push_point": push})
    except ValueError:
        return None
    return {"blocks": blocks, "push": push, "edit": detail, "parent_id": parent.get("id"),
            "hash": digest([blocks, push])}


def features(seed, parent, proposal):
    before, after = metrics(parent["blocks"]), metrics(proposal["blocks"])
    edit = proposal["edit"]
    position = edit["before"]["position"]
    return [seed["width"] / 16, seed["height"] / 16, before[0] / 16, before[1] / 128,
            len(seed["request"]["targets"]) / 32, (after[0] - before[0]) / 4, (after[1] - before[1]) / 8,
            position["x"] / max(1, seed["width"] - 1), position["y"] / max(1, seed["height"] - 1), position["z"] / 16,
            *[float(edit["operation"] == op) for op in OPERATIONS],
            *[float(edit["before"]["block"]["kind"] == kind) for kind in KINDS],
            *[float((edit.get("after") or {}).get("block", {}).get("kind") == kind) for kind in KINDS]]


FEATURE_NAMES = ["截面宽", "截面高", "父厚度", "父方块数", "目标数", "厚度变化", "方块数变化", "修改X", "修改Y", "修改Z",
                 *[f"操作_{op}" for op in OPERATIONS], *[f"原方块_{k}" for k in KINDS], *[f"新方块_{k}" for k in KINDS]]

"""截面等距变换和材料互换；后代始终继承来源划分。"""

from copy import deepcopy

from ..serialization import digest


def transform(record, swap=False, sx=1, sy=1, materials=False, offset=0):
    row = deepcopy(record)
    task = row["task"]
    width, height = (task["height"], task["width"]) if swap else (task["width"], task["height"])

    def point(p):
        x, y = (p["y"], p["x"]) if swap else (p["x"], p["y"])
        return {**p, "x": (x if sx == 1 else width-1-x)+offset,
                "y": (y if sy == 1 else height-1-y)+offset}

    for block in row["proposal"]["blocks"]:
        block["position"] = point(block["position"])
        spec = block["block"]
        sign, axis = spec["facing"].split("_")
        if axis != "z":
            if swap:
                axis = "y" if axis == "x" else "x"
            direction = (1 if sign == "positive" else -1)*(sx if axis == "x" else sy)
            spec["facing"] = ("positive_" if direction > 0 else "negative_")+axis
        if materials:
            spec["kind"] = {"slime_block": "honey_block", "honey_block": "slime_block"}.get(spec["kind"], spec["kind"])
    row["proposal"]["push"] = point(row["proposal"]["push"])
    task["targets"] = sorted([point(t) for t in task["targets"]], key=lambda t: (t["x"], t["y"]))
    task.update(width=width+offset, height=height+offset)
    row["id"] = digest([task, row["proposal"]])[:24]
    row["task_id"] = digest(task)[:24]
    return row

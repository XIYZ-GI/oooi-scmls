from app.models.push_point import resolve_push_point


def rotate(position, forward):
    x, y, z = position["x"], position["y"], position["z"]
    values = {
        "positive_z": (x, y, z), "negative_z": (-x, y, -z),
        "positive_x": (-z, y, x), "negative_x": (z, y, -x),
        "positive_y": (x, -z, y), "negative_y": (x, z, -y),
    }[forward]
    return dict(zip(("x", "y", "z"), values))


def normalize_structure(sample):
    vectors = {
        "positive_x": (1, 0, 0), "negative_x": (-1, 0, 0),
        "positive_y": (0, 1, 0), "negative_y": (0, -1, 0),
        "positive_z": (0, 0, 1), "negative_z": (0, 0, -1),
    }
    rotated = []
    for block in sample["blocks"]:
        direction = rotate(dict(zip(("x", "y", "z"), vectors[block["facing"]])), sample["forward"])
        facing = next(key for key, vector in vectors.items() if vector == tuple(direction.values()))
        rotated.append({**block, "position": rotate(block["position"], sample["forward"]), "facing": facing})
    minimum = {axis: min(block["position"][axis] for block in rotated) for axis in ("x", "y", "z")}
    maximum = {axis: max(block["position"][axis] for block in rotated) for axis in ("x", "y", "z")}
    for block in rotated:
        pos = block["position"]
        block["position"] = {"x": pos["x"] - minimum["x"], "y": pos["y"] - minimum["y"], "z": pos["z"] - maximum["z"] - 2}
    return {"blocks": rotated, "width": maximum["x"] - minimum["x"] + 1, "height": maximum["y"] - minimum["y"] + 1, "depth": maximum["z"] - minimum["z"] + 1}


def annotation_error(sample):
    if sample.get("pushPoint") is None:
        return "请标注一个推动点"
    if not sample.get("targets"):
        return "请至少标注一个被推动的目标点"
    shape = normalize_structure(sample)
    try:
        point = resolve_push_point([(block["position"]["x"], block["position"]["y"], block["position"]["z"]) for block in shape["blocks"]], sample["pushPoint"])
    except ValueError as error:
        return str(error)
    if not any(block["layer"] == 0 and block["position"] == point for block in shape["blocks"]):
        return "推动点必须对应主层的移动线方块"
    return None

import math
from app.models.load_protocol import TARGET_LOAD_BLOCKS, LOAD_TIMING_PROTOCOL, MIN_TARGET_Z, MAX_TARGET_Z
from app.models.push_point import resolve_push_point

from .constants import BLOCK_KINDS, DIRECTIONS, MAX_AXIS, MAX_BLOCKS, MAX_VOLUME
from .coordinates import annotation_error, normalize_structure


def integer(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def validate_document(kind, value):
    if not isinstance(value, dict):
        raise ValueError("结构数据必须是对象")
    name = value.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise ValueError("名称不能为空，且不能超过 120 字符")
    blocks = value.get("blocks")
    if not isinstance(blocks, list) or len(blocks) > MAX_BLOCKS:
        raise ValueError("方块列表无效或超过 4096 个方块")
    if kind == "scenes":
        seen = set()
        for block in blocks:
            if not isinstance(block, dict) or not isinstance(block.get("position"), dict) or not isinstance(block.get("block"), dict):
                raise ValueError("结构方块格式无效")
            position, spec = block["position"], block["block"]
            if any(not integer(position.get(axis), -30000, 30000) for axis in ("x", "y", "z")) or spec.get("kind") not in BLOCK_KINDS or spec.get("facing") not in DIRECTIONS:
                raise ValueError("结构包含无效坐标、方块或朝向")
            key = tuple(position[axis] for axis in ("x", "y", "z"))
            if key in seen:
                raise ValueError("结构坐标重复")
            seen.add(key)
        return {"name": name.strip(), "blocks": blocks}
    size = value.get("sourceSize")
    origin = value.get("sourceOrigin")
    if not isinstance(size, list) or len(size) != 3 or any(not integer(n, 1, MAX_AXIS) for n in size) or math.prod(size) > MAX_VOLUME:
        raise ValueError("原始结构尺寸无效")
    if not isinstance(origin, list) or len(origin) != 3 or any(not integer(n, -(2**53 - 1), 2**53 - 1) for n in origin):
        raise ValueError("原始世界坐标无效")
    if value.get("forward") not in DIRECTIONS or not blocks:
        raise ValueError("前进方向或方块数量无效")
    for key, limit in (("fileName", 300), ("author", 300), ("notes", 5000)):
        if not isinstance(value.get(key), str) or len(value[key]) > limit:
            raise ValueError(f"{key} 格式错误或过长")
    seen = set()
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("position"), dict):
            raise ValueError("方块格式无效")
        position = block["position"]
        if any(not integer(position.get(axis), 0, size[index] - 1) for index, axis in enumerate(("x", "y", "z"))) or not integer(block.get("layer"), 0, 1):
            raise ValueError("方块坐标或所在层无效")
        if not isinstance(block.get("name"), str) or block.get("kind") not in BLOCK_KINDS | {None} or block.get("facing") not in DIRECTIONS:
            raise ValueError("方块类型或朝向无效")
        states = block.get("states")
        if not isinstance(states, dict) or any(type(state) not in (int, float, str, bool) or (isinstance(state, float) and not math.isfinite(state)) for state in states.values()):
            raise ValueError("方块状态无效")
        key = (block["layer"], position["x"], position["y"], position["z"])
        if key in seen:
            raise ValueError("方块坐标重复")
        seen.add(key)
    if not any(block["layer"] == 0 for block in blocks):
        raise ValueError("结构缺少主层方块")
    shape = normalize_structure(value)
    def valid_point(point):
        return isinstance(point, dict) and integer(point.get("x"), 0, shape["width"] - 1) and integer(point.get("y"), 0, shape["height"] - 1)
    push = value.get("pushPoint")
    targets = value.get("targets")
    if (push is not None and not valid_point(push)) or not isinstance(targets, list) or any(not valid_point(point) for point in targets):
        raise ValueError("推动点或目标点无效")
    if push is not None:
        if push.get("z") is not None and not integer(push["z"], -129, -2):
            raise ValueError("推动点前后位置无效")
        push = resolve_push_point([(block["position"]["x"], block["position"]["y"], block["position"]["z"]) for block in shape["blocks"]], push)
        if not any(block["layer"] == 0 and block["position"] == push for block in shape["blocks"]):
            raise ValueError("推动点必须对应主层的移动线方块")
    if len(targets) > MAX_BLOCKS or any(not integer(point.get("z", 0), MIN_TARGET_Z, MAX_TARGET_Z) for point in targets):
        raise ValueError("目标数量过多或目标前后位置无效")
    for point in targets:
        if any(block["position"]["x"] == point["x"] and block["position"]["y"] == point["y"] and block["position"]["z"] >= point.get("z", 0) for block in shape["blocks"]):
            raise ValueError(f"目标 ({point['x']}, {point['y']}) 的负载必须放在这一列移动线方块的前方")
    if len({(point["x"], point["y"]) for point in targets}) != len(targets):
        raise ValueError("目标点重复")
    if type(value.get("completed")) is not bool:
        raise ValueError("标注完成状态无效")
    if value["completed"] and annotation_error(value):
        raise ValueError(annotation_error(value))
    result = {key: value[key] for key in ("fileName", "sourceSize", "sourceOrigin", "blocks", "forward", "pushPoint", "author", "notes", "completed")}
    result.update(name=name.strip(), targets=[{"x": point["x"], "y": point["y"], "z": point.get("z", 0)} for point in targets], timing=value.get("timing"))
    result["pushPoint"] = push
    timing = result["timing"]
    if isinstance(timing, dict) and (timing.get("protocol") != LOAD_TIMING_PROTOCOL or timing.get("loadBlocks") != TARGET_LOAD_BLOCKS):
        result["timing"] = timing = None
    if timing is not None:
        if not isinstance(timing, dict) or timing.get("status") not in ("success", "failed") or not isinstance(timing.get("targets"), list):
            raise ValueError("时序结果格式无效")
        if {(p.get("x"), p.get("y"), p.get("z")) for p in timing["targets"] if isinstance(p, dict)} != {(p["x"], p["y"], p.get("z", 0)) for p in targets}:
            raise ValueError("时序结果与目标点不一致")
        if len(timing["targets"]) != len(targets) or any(not isinstance(timing.get(key), str) for key in ("reason", "protocol", "engineVersion", "computedAt")):
            raise ValueError("时序结果缺少说明或包含重复目标")
        if any(not integer(timing.get(key), 0, 2000) for key in ("simulatedTicks", "maxTicks", "pulseTicks")):
            raise ValueError("时序结果的游戏刻无效")
        for point in timing["targets"]:
            if "error" in point and not isinstance(point["error"], str):
                raise ValueError("目标异常原因必须是文本")
            if "failed" in point and type(point["failed"]) is not bool:
                raise ValueError("目标失败标记必须是布尔值")
            if not integer(point.get("movedBlocks"), 0, TARGET_LOAD_BLOCKS):
                raise ValueError("目标负载推动数量无效")
            if not valid_point(point) or any(key not in point or (point[key] is not None and not integer(point[key], 0 if key == "tick" else 1, 2000)) for key in ("tick", "order")):
                raise ValueError("目标时序无效")
            if timing["status"] == "success" and (point["tick"] is None or point["order"] is None):
                raise ValueError("成功时序必须包含所有目标的完成刻与分组")
            if point["tick"] is not None and point["movedBlocks"] != TARGET_LOAD_BLOCKS and not (timing["status"] == "failed" and point.get("error")):
                raise ValueError("目标必须推动全部十个负载方块才能记录完成刻")
    return result

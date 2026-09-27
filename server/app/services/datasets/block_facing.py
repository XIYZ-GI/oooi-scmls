from .constants import DIRECTIONS, NAMED_DIRECTIONS, PISTON_DIRECTIONS


def imported_block_facing(kind, states):
    """兼容数字及文字朝向，观察者转换为引擎使用的输出端方向。"""
    value = states.get("minecraft:facing_direction", states.get("facing_direction", 3))
    if isinstance(value, str):
        if value not in NAMED_DIRECTIONS:
            raise ValueError(f"结构包含未知方块朝向：{value}")
        facing = NAMED_DIRECTIONS[value]
    else:
        directions = PISTON_DIRECTIONS if kind in ("piston", "sticky_piston") else DIRECTIONS
        facing = directions[value] if isinstance(value, int) and 0 <= value < 6 else "positive_z"
    cardinal = states.get("minecraft:cardinal_direction")
    facing = NAMED_DIRECTIONS.get(cardinal, facing)
    if kind == "observer":
        facing = ("negative" if facing.startswith("positive") else "positive") + facing[facing.index("_"):]
    return facing

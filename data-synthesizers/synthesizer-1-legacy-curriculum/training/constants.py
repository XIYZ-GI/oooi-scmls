"""阶段一的词表与完整运行协议。"""

DIRECTIONS = ("positive_x", "negative_x", "positive_y", "negative_y", "positive_z", "negative_z")
STATES = [("air", "positive_z")]
STATES += [(kind, "positive_z") for kind in (
    "slime_block", "honey_block", "redstone_block", "iron_block", "light_blue_glazed_terracotta", "glass")]
STATES += [(kind, facing) for kind in ("piston", "sticky_piston", "observer") for facing in DIRECTIONS]
STATE_IDS = {state: i for i, state in enumerate(STATES)}
BOS = len(STATES)
PROTOCOL = "generation_fixed_cycle_load10_v1"
AXES = ("x", "y", "z")

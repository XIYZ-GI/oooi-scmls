from .constants import BLOCK_KINDS


def map_imported_block(name: str) -> str:
    """把结构文件的方块名称映射为模拟器支持的类型，原始名称另行保留。"""
    key = name.removeprefix("minecraft:")
    if key == "slime":
        return "slime_block"
    if key == "glazed_terracotta" or key.endswith("_glazed_terracotta"):
        return "light_blue_glazed_terracotta"
    return key if key in BLOCK_KINDS else "iron_block"

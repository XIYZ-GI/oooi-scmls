"""可复现的 JSON、任务指纹与空间编码。"""

import hashlib
import json
from pathlib import Path

from .constants import AXES, STATE_IDS, STATES


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def positions(task):
    # 每列从后向前，然后遍历截面；空位也必须由模型预测。
    return [(x, y, z) for x in range(task["width"]) for y in range(task["height"])
            for z in range(-task["depth"] - 1, -1)]


def encode_structure(task, blocks, push):
    lookup = {tuple(b["position"][a] for a in AXES): b["block"] for b in blocks}
    grid = positions(task)
    tokens = []
    for p in grid:
        block = lookup.get(p)
        if block is None:
            tokens.append(0)
        else:
            facing = block["facing"] if block["kind"] in ("piston", "sticky_piston", "observer") else "positive_z"
            tokens.append(STATE_IDS[(block["kind"], facing)])
    if len(lookup) != sum(t != 0 for t in tokens):
        raise ValueError("答案结构超出初始空间或含重复坐标")
    return tokens, grid.index(tuple(push[a] for a in AXES))


def decode_structure(task, tokens, push_index):
    grid = positions(task)
    if len(tokens) != len(grid) or not 0 <= push_index < len(grid):
        raise ValueError("生成序列长度或推动点编号错误")
    blocks = [{"position": dict(zip(AXES, p)), "block": {"kind": STATES[t][0], "facing": STATES[t][1]}}
              for p, t in zip(grid, tokens) if t != 0]
    return {"blocks": blocks, "push": dict(zip(AXES, grid[push_index]))}

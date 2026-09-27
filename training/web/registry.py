"""模型版本注册表；历史任务固定引用发布时的版本编号与权重摘要。

注册表是纯 JSON，不依赖数据库：``models.json`` 里每一条对应一个可选的生成模型，
``default`` 指定默认版本。权重路径相对模型目录解析，越界或摘要不一致都会被拒绝。
"""

import hashlib
import json

from .config import MODELS, REGISTRY


def entries():
    data = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"models": []}
    rows = list(data.get("models", []))
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("模型版本编号重复")
    for row in rows:
        path = (MODELS / row["path"]).resolve()
        if not path.is_relative_to(MODELS.resolve()):
            raise ValueError("模型路径超出模型目录")
        row["ready"] = row.get("enabled", True) and path.is_file()
        row["device"] = "cpu"
    return rows, data.get("default")


def catalog():
    rows, default = entries()
    return dict(models=[{k: v for k, v in row.items() if k != "path"} for row in rows], default=default)


def get(model_id=None):
    rows, default = entries()
    wanted = model_id or default
    row = next((row for row in rows if row["id"] == wanted), None)
    if row is None:
        raise ValueError("模型版本不存在，请重新载入")
    return row


def path_for(entry):
    return MODELS / entry["path"]


def digest(path):
    """权重文件的 SHA-256，用于校验注册表条目与磁盘内容一致。"""
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def conditioning(config):
    """从网络配置推出「哪些需求字段真的进入模型」，供网页隐藏无效果的输入框。

    ``use_run_features`` 关闭时每轮刻数、连续轮数与每目标负载数都不进网络，它们只
    决定验收标准；``use_target_z`` 关闭时目标 z 也不进网络。
    """
    runs = bool(config.get("use_run_features", True))
    return dict(size=True, targets=True, max_ticks=runs, rounds=runs, load_blocks=runs,
                target_z=bool(config.get("use_target_z", True)))

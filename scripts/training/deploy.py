"""把训练好的检查点发布到 ``models/`` 并更新网页生成服务的注册表。

只搬运推理需要的字段（网络、权重、步数、种子、参数量），去掉优化器状态，权重
按版本编号命名，摘要写进 ``models.json``。生成服务启动时按摘要校验文件，摘要不一致
直接拒绝加载，避免注册表和磁盘上的权重对不上。
"""

import argparse
import hashlib
import json
from pathlib import Path

import torch

from training.serialization import write_json
from training.web.config import REGISTRY
from training.web.registry import conditioning

KEEP = ("model", "config", "step", "seed", "parameters")


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def main(checkpoint, model_id, name, status, models_dir, protocol="eight_view_greedy_v1", default=False):
    checkpoint, models_dir = Path(checkpoint), Path(models_dir)
    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    missing = [key for key in KEEP if key not in saved]
    if missing:
        raise SystemExit(f"检查点缺少字段：{missing}")
    value = {key: saved[key] for key in KEEP}
    value["protocol"] = protocol
    models_dir.mkdir(parents=True, exist_ok=True)
    published = models_dir / f"{model_id}.pt"
    staging = published.with_suffix(".staging.pt")
    torch.save(value, staging)
    staging.replace(published)
    entry = dict(id=model_id, name=name, architecture="autoregressive_v1", path=published.name,
                 checkpoint_sha256=digest(published), parameters=int(value["parameters"]["total"]),
                 enabled=True, protocol=protocol, status=status, conditioning=conditioning(value["config"]))
    registry = models_dir / "models.json" if models_dir != REGISTRY.parent else REGISTRY
    data = json.loads(registry.read_text()) if registry.exists() else dict(models=[], default=None)
    data["models"] = [row for row in data.get("models", []) if row["id"] != model_id] + [entry]
    if default or data.get("default") is None:
        data["default"] = model_id
    write_json(registry, data)
    print(json.dumps(dict(entry=entry, default=data["default"]), ensure_ascii=False), flush=True)
    return entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--status", required=True, help="写进注册表的成绩或说明")
    parser.add_argument("--models-dir", default="models")
    parser.add_argument("--default", action="store_true", help="把该版本设为网页默认模型")
    args = parser.parse_args()
    main(args.checkpoint, args.model_id, args.name, args.status, args.models_dir, default=args.default)

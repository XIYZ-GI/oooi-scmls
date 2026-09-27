"""从需求构造模型输入；生成时不读取答案结构。"""

import json
from pathlib import Path

import torch

from .constants import BOS
from .domain_rules import filter_examples
from .serialization import encode_structure, positions

# 需求特征分三段：几何九项、目标三项、运行协议三项；历史口径另有目标 z 两项。
GEOMETRY_COLUMNS = 9
TARGET_COLUMNS = 3
RUN_COLUMNS = 3
TARGET_Z_WIDTH = 2
FEATURES = GEOMETRY_COLUMNS + TARGET_COLUMNS + RUN_COLUMNS + TARGET_Z_WIDTH
# 历史口径里目标点 z 两列的列号，插入位置紧跟“是否目标”，此处只用于兼容读取。
TARGET_Z_COLUMNS = (10, 11)


def feature_count(use_target_z=True, use_run_features=True):
    """按模型口径计算条件向量列数：无目标 z 且无运行协议时是十二维。"""
    return (GEOMETRY_COLUMNS + TARGET_COLUMNS + (TARGET_Z_WIDTH if use_target_z else 0)
            + (RUN_COLUMNS if use_run_features else 0))


def condition(task, use_target_z=True, use_run_features=True, zero_target_z=False):
    grid = positions(task)
    targets = {(t["x"], t["y"]): t for t in task["targets"]}
    rows = []
    for x, y, z in grid:
        target = targets.get((x, y))
        row = [x/8, y/8, z/8, task["width"]/8, task["height"]/8, task["depth"]/8,
               (x+0.5)/task["width"], (y+0.5)/task["height"], (z+task["depth"]+1)/task["depth"],
               float(target is not None)]
        # 目标点 z 只是负载在场景里的摆放位置，不影响推动时序；不需要 z 的模型根本不带这两维。
        if use_target_z:
            row += ([0, 0] if zero_target_z else
                    [target["z"]/8 if target else 0, (target["z"]-z)/8 if target else 0])
        row += [target["order"]/4 if target else 0, len(targets)/8]
        # 每轮刻数、连续轮数、每目标负载数三项与数据来源共线，实测被模型当成来源标签，
        # 已经从新模型的输入里去掉；旧检查点仍按 use_run_features=True 读取同样三列。
        if use_run_features:
            row += [task["max_ticks"]/200, task["rounds"]/10, task["load_blocks"]/12]
        rows.append(row)
    return torch.tensor(rows, dtype=torch.float32), torch.tensor(grid, dtype=torch.long)


def batch_tasks(tasks, device, use_target_z=True, use_run_features=True):
    values = [condition(task, use_target_z, use_run_features) for task in tasks]
    length = max(len(v[0]) for v in values)
    width = feature_count(use_target_z, use_run_features)
    features = torch.zeros(len(tasks), length, width)
    coords = torch.zeros(len(tasks), length, 3, dtype=torch.long)
    padding = torch.ones(len(tasks), length, dtype=torch.bool)
    for i, (f, c) in enumerate(values):
        features[i, :len(f)] = f
        coords[i, :len(c)] = c
        padding[i, :len(f)] = False
    return {"features": features.to(device), "coords": coords.to(device), "padding": padding.to(device)}


def collate(records, device, use_target_z=True, use_run_features=True):
    result = batch_tasks([r["task"] for r in records], device, use_target_z, use_run_features)
    shape = result["padding"].shape
    labels = torch.full(shape, -100, dtype=torch.long)
    inputs = torch.full(shape, BOS, dtype=torch.long)
    pushes = []
    for i, record in enumerate(records):
        tokens, push = encode_structure(record["task"], **record["proposal"])
        labels[i, :len(tokens)] = torch.tensor(tokens)
        inputs[i, 1:len(tokens)] = torch.tensor(tokens[:-1])
        pushes.append(push)
    result.update(labels=labels.to(device), inputs=inputs.to(device), pushes=torch.tensor(pushes, device=device))
    return result


def read_examples(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return filter_examples(rows, str(path))

import math

import numpy as np

from app.repositories.library import now
from .mutations import FEATURE_NAMES


def predict(model, features):
    if not model or model.get("status") != "trained":
        return 0.5
    value = model["weights"][0] + sum(w * x for w, x in zip(model["weights"][1:], features))
    return 1 / (1 + math.exp(-max(-30, min(30, value))))


def fit_model(job, records):
    splits = {s["id"]: s["split"] for s in job["seeds"]}
    train = [r for r in records if splits[r["seed_id"]] == "train" and "error" not in r["result"]]
    positive = sum(bool(r["result"].get("load_pass")) for r in train)
    model = {"status": "waiting", "kind": "logistic_edit_ranker", "label": "首轮十块负载及时序通过",
             "featureVersion": 1, "features": FEATURE_NAMES, "trainedAt": now(),
             "trainRows": len(train), "positive": positive, "negative": len(train) - positive,
             "guidance": "仅给训练来源候选排序；每批保留 30% 随机探索，所有候选仍由模拟器判定"}
    if positive < 3 or len(train) - positive < 3:
        model["reason"] = "正负训练记录各至少需要三条，继续采集即可"
        return model
    x = np.asarray([[1, *r["features"]] for r in train], dtype=float)
    y = np.asarray([float(r["result"].get("load_pass", False)) for r in train])
    weights = np.zeros(x.shape[1])
    balance = np.where(y == 1, len(y) / (2 * positive), len(y) / (2 * (len(y) - positive)))
    for _ in range(400):
        prediction = 1 / (1 + np.exp(-np.clip(x @ weights, -30, 30)))
        gradient = x.T @ ((prediction - y) * balance) / len(y)
        gradient[1:] += 0.02 * weights[1:]
        weights -= 0.15 * gradient
    model.update(status="trained", weights=weights.tolist())
    # 保留测试来源不参与训练与在线排序；只报告验证来源表现。
    validation = [r for r in records if splits[r["seed_id"]] == "validation" and "error" not in r["result"]]
    if validation:
        labels = [int(r["result"].get("load_pass", False)) for r in validation]
        prediction = [predict(model, r["features"]) >= 0.5 for r in validation]
        model["validation"] = {"rows": len(labels), "positive": sum(labels),
                               "accuracy": sum(p == y for p, y in zip(prediction, labels)) / len(labels),
                               "majorityBaseline": max(sum(labels), len(labels) - sum(labels)) / len(labels)}
    return model

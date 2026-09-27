"""冻结第三阶段数据、原来源划分及训练前实验计划。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import time

from ..prepare import simulate_example
from ..serialization import digest, write_json
from ..templates import geometry_key
from .curriculum import pull_rules, strong_rules
from .transforms import transform


def main():
    root = Path("data/generation/stage3")
    root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    experts = json.loads(Path("data/generation/stage1/expert-snapshot.json").read_text())
    old = [json.loads(line) for line in Path("data/generation/stage1/examples.jsonl").read_text().splitlines()]
    old_geometry = {}
    for row in old:
        key = digest(geometry_key([(t["x"], t["y"], t["z"], t["order"]) for t in row["task"]["targets"]]))
        if key in old_geometry and old_geometry[key] != row["split"]:
            raise ValueError("旧课程相同目标几何跨集合")
        old_geometry[key] = row["split"]
    records, reserved = [], {}
    for expert in experts:
        targets = [{k: t[k] for k in ("x", "y", "z", "order")} for t in expert["reference"]["targets"]]
        geometry = digest(geometry_key([(t["x"], t["y"], t["z"], t["order"]) for t in targets]))
        reserved[geometry] = True
        row = {"task": {"width": expert["width"], "height": expert["height"], "depth": expert["depth"],
                       "targets": targets, "max_ticks": expert["request"]["max_ticks"], "rounds": 3, "load_blocks": 10},
               "proposal": {"blocks": expert["request"]["blocks"], "push": expert["request"]["push_point"]},
               "family": "expert_compact", "group": "expert-"+expert["group"], "split": expert["split"],
               "source": expert["id"], "source_name": expert["name"]}
        for swap in (False, True):
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for materials in (False, True):
                        records.append(transform(row, swap, sx, sy, materials))
    # 防止课程与专家的相同目标几何被分配到不同集合。
    rules = [r for r in strong_rules() if r["group"].removeprefix("strong-") not in reserved]
    for row in rules:
        key = row["group"].removeprefix("strong-")
        if key in old_geometry:
            row["split"] = old_geometry[key]
    pull_source = next(e for e in experts if e["name"] == "移动线12")
    assert pull_source["split"] == "train"
    rules += list(pull_rules("expert-"+pull_source["group"]))
    for row in rules:
        for swap, sx, sy, material, offset in (
            (False, 1, 1, False, 0), (True, 1, 1, False, 0),
            (False, -1, 1, True, 0), (True, -1, -1, True, 0),
            (False, 1, 1, False, 1), (True, 1, 1, True, 1),
        ):
            records.append(transform(row, swap, sx, sy, material, offset))
    records = list({r["id"]: r for r in records}.values())
    accepted, rejected = [], []
    with ProcessPoolExecutor(max_workers=4) as pool:
        for i, row in enumerate(pool.map(simulate_example, records, chunksize=4)):
            (accepted if row["evaluation"]["accepted"] else rejected).append(row)
            if (i+1) % 100 == 0:
                print(json.dumps({"完成": i+1, "有效": len(accepted), "总数": len(records)}, ensure_ascii=False), flush=True)
    for r in old:
        r["family"] = "legacy_"+r["family"]
    accepted += old
    groups, tasks = {}, {}
    for row in accepted:
        for index, key in ((groups, row["group"]), (tasks, row["task_id"])):
            if key in index and index[key] != row["split"]:
                raise RuntimeError("来源或相同需求跨集合")
            index[key] = row["split"]
    with (root/"examples.jsonl").open("w") as handle:
        for row in accepted:
            handle.write(json.dumps(row, ensure_ascii=False)+"\n")
    write_json(root/"rejected.json", [{"id": r["id"], "family": r["family"], "reason": r["evaluation"]["reason"]} for r in rejected])
    write_json(root/"manifest.json", {"examples": len(accepted), "attempted_new": len(records), "rejected_new": len(rejected),
        "by_split_family": dict(Counter(r["split"]+"/"+r["family"] for r in accepted)),
        "groups": {s: len({r["group"] for r in accepted if r["split"] == s}) for s in ("train", "validation", "test")},
        "examples_sha256": digest((root/"examples.jsonl").read_text()), "seconds": time.monotonic()-started,
        "scope": "强充能课程按目标几何分组，原理族共享；拉驱规则继承训练成品来源，独立迁移由保留专家来源评价；成品变换不算独立新设计。"})
    write_json(root/"experiment-plan.json", {"stage": 3, "seed": 20260925, "steps": 6000, "batch_size": 12,
        "initial_checkpoint": "runs/stage2/baseline-20260921/best.pt", "learning_rate": 0.00015,
        "family_sampling": {"strong_compact": 0.4, "pull_compact": 0.2, "expert_compact": 0.25, "legacy": 0.15},
        "selection": "每500步按验证集合的分族平均结构损失选模，不用保留成绩选模。",
        "evaluation": "冻结后，同预算比较旧模型与新模型；40个强充能新几何需求、全部3个保留专家来源各2个变换、16个旧推驱需求；每需求8候选。",
        "diagnostic": "另报训练来源拉驱规则上的构造能力，明确不作为独立泛化。",
        "goals": "独立强充能需求产生两格有效结构；诊断回拉、强充能、混合材料与多时序；各项分别报告，不以同推成功代替完整第三阶段完成。",
        "max_training_seconds": 3600, "new_training_runs": 1})
    print((root/"manifest.json").read_text(), flush=True)


if __name__ == "__main__":
    main()

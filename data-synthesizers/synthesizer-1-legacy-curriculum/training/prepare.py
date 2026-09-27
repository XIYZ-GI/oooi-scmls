"""冻结课程任务、精确模拟标签和已有成品的过程记录。"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import time

from .constants import PROTOCOL
from .evaluator import evaluate
from .serialization import digest, write_json
from .templates import candidates


def simulate_example(record):
    result = evaluate(record["task"], record["proposal"])
    record["evaluation"] = result
    record["id"] = digest([record["task"], record["proposal"]])[:24]
    record["task_id"] = digest(record["task"])[:24]
    return record


def main():
    parser = argparse.ArgumentParser(description="制作阶段一的课程数据及运行轨迹")
    parser.add_argument("--output", default="data/generation/stage1")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    records = list(candidates())
    # 按族分层，再按整个几何来源划分；保证验证集合也包含接力任务。
    split_by_group = {}
    for family in sorted({r["family"] for r in records}):
        family_groups = sorted({r["group"] for r in records if r["family"] == family})
        held = max(1, len(family_groups)//6)
        for rank, group in enumerate(family_groups):
            split_by_group[group] = "validation" if rank < held else "test" if rank < 2*held else "train"
    for record in records:
        record["split"] = split_by_group[record["group"]]
    write_json(output / "experiment-plan.json", {
        "protocol": PROTOCOL, "seed": 20260920, "rounds": 3, "load_blocks": 10,
        "cycle_ticks": 32, "candidate_budget_per_task": 8, "evaluation_sampling_seeds": [41, 97],
        "max_evaluation_tasks_per_split": 80, "steps_per_run": 4000, "max_gpu_hours": 4,
        "maximum_quoted_hourly_yuan": 3, "max_training_attempts": 3,
        "success_gate": "两个独立采样种子均在至少十个保留的新几何需求上通过完整三轮；至少包含同时推动和两级接力两类。",
        "scope": "新几何参数组合；构造规则族在训练中出现，不宣称跨原理或复杂专家任务泛化",
        "selection": "只使用训练和验证集合调参，保留集合只在最终检查点冻结后评估",
    })
    accepted, failures = [], Counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, record in enumerate(pool.map(simulate_example, records, chunksize=8)):
            if record["evaluation"]["accepted"]:
                accepted.append(record)
            else:
                failures[record["evaluation"]["reason"]] += 1
            if (i+1) % 250 == 0:
                print(json.dumps({"已模拟": i+1, "有效": len(accepted)}, ensure_ascii=False), flush=True)
    with (output / "examples.jsonl").open("w") as handle:
        for record in accepted:
            handle.write(json.dumps(record, ensure_ascii=False)+"\n")
    groups = {s: {r["group"] for r in accepted if r["split"] == s} for s in ("train", "validation", "test")}
    tasks = {s: {r["task_id"] for r in accepted if r["split"] == s} for s in groups}
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if groups[left] & groups[right] or tasks[left] & tasks[right]:
            raise RuntimeError("来源或需求跨集合泄漏")
    # 每个几何来源留一个完整轨迹，所有记录均保留三轮完成时间。
    selected = {}
    for record in accepted:
        selected.setdefault(record["group"], record)
    with gzip.open(output / "curriculum-traces.jsonl.gz", "wt") as handle:
        for record in selected.values():
            handle.write(json.dumps({"id": record["id"], "group": record["group"], "split": record["split"],
                                     "result": evaluate(record["task"], record["proposal"], True)}, ensure_ascii=False)+"\n")
    experts_path = output / "expert-snapshot.json"
    expert_results = []
    if experts_path.exists():
        with gzip.open(output / "expert-traces.jsonl.gz", "wt") as handle:
            for expert in json.loads(experts_path.read_text()):
                targets = [{k: p[k] for k in ("x", "y", "z", "order")} for p in expert["reference"]["targets"]]
                task = {"width": expert["width"], "height": expert["height"], "depth": expert["depth"], "targets": targets,
                        "max_ticks": expert["request"]["max_ticks"], "rounds": 3, "load_blocks": 10}
                result = evaluate(task, {"blocks": expert["request"]["blocks"], "push": expert["request"]["push_point"]}, True)
                handle.write(json.dumps({"source_id": expert["id"], "split": expert["split"], "result": result}, ensure_ascii=False)+"\n")
                expert_results.append({"id": expert["id"], "accepted_fixed_cycle": result["accepted"], "reason": result["reason"]})
    manifest = {"protocol": PROTOCOL, "examples_sha256": digest((output / "examples.jsonl").read_text()),
                "attempted": len(records), "accepted": len(accepted), "failures": dict(failures),
                "splits": {s: {"examples": sum(r["split"] == s for r in accepted), "groups": len(groups[s]), "tasks": len(tasks[s])} for s in groups},
                "families": dict(Counter(r["family"] for r in accepted)), "seconds": time.monotonic()-started,
                "expert_protocol_observations": expert_results,
                "expert_training_usage": "本阶段专家来源冻结并采集轨迹，不将超出小任务课程的专家成品强行加入监督损失。",
                "trace_coverage": "逐命令保存方块、阶段期限、运动组、活塞臂与去重事件；没有可靠因果来源的信号关系不生成监督标签。"}
    write_json(output / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

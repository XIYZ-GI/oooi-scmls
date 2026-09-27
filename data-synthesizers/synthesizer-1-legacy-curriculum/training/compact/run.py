"""固定需求与检查点后，对第三阶段完整生成进行分项对照。"""

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ..data import read_examples
from ..serialization import digest, write_json
from .splits import reconcile


def choose(rows, limit):
    groups = defaultdict(list)
    for row in {r["task_id"]: r for r in rows}.values():
        groups[row["group"]].append(row)
    for values in groups.values():
        values.sort(key=lambda r: digest(["stage3_fixed", r["task_id"]]))
    selected = []
    for index in range(max((len(v) for v in groups.values()), default=0)):
        for group in sorted(groups):
            if index < len(groups[group]):
                selected.append(groups[group][index])
    return selected[:limit]


def execute(args, log):
    with Path(log).open("w") as handle:
        subprocess.run([sys.executable, *args], stdout=handle, stderr=subprocess.STDOUT, check=True)


def main():
    data = Path("data/generation/stage3")
    root = Path("runs/stage3")
    root.mkdir(parents=True, exist_ok=True)
    records = reconcile(data)
    summary_path = root/"training-summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        if summary["data_digest"] != digest((data/"examples.jsonl").read_text()):
            raise ValueError("已有训练产物的数据版本不同，请使用独立实验目录")
        if summary["plan"] != json.loads((data/"experiment-plan.json").read_text()):
            raise ValueError("已有训练产物的计划不同，禁止复用旧检查点冒充新训练")
    selected = []
    for count, limit in ((2, 8), (3, 8), (4, 8), (5, 8), (6, 4), (7, 4)):
        selected += choose([r for r in records if r["split"] == "test" and r["family"] == "strong_compact"
                            and len(r["task"]["targets"]) == count], limit)
    for group in sorted({r["group"] for r in records if r["family"] == "expert_compact" and r["split"] == "test"}):
        selected += choose([r for r in records if r["group"] == group and r["family"] == "expert_compact"], 2)
    selected += choose([r for r in records if r["split"] == "test" and r["family"].startswith("legacy_")], 16)
    # 拉驱训练来源上的单独诊断，不混入保留评估或成功门槛。
    diagnostic = choose([r for r in records if r["family"] == "pull_compact"], 12)
    for name, rows in (("heldout", selected), ("diagnostic", diagnostic)):
        path = data/(name+".jsonl")
        content = "".join(json.dumps({**r, "split": "test"}, ensure_ascii=False)+"\n" for r in rows)
        if path.exists() and path.read_text() != content:
            raise ValueError("已冻结的评估需求不可替换")
        path.write_text(content)
    write_json(root/"evaluation-plan.json", {"tasks": [{k: r[k] for k in ("task_id", "family", "group", "task")} for r in selected],
        "diagnostic_task_ids": [r["task_id"] for r in diagnostic], "candidate_budget": 8, "sampling_seed": 41,
        "gate": "新模型强充能保留成功至少10个且优于旧模型，覆盖4目标和5目标；独立专家拉驱/多时序及诊断另报，不以局部门槛宣称整个第三阶段完成。"})
    if not (root/"training-summary.json").exists():
        print("开始第三阶段迁移训练", flush=True)
        execute(["-m", "training.compact.train"], root/"training.log")
    baseline = "runs/stage2/baseline-20260921/best.pt"
    checkpoints = {"baseline": baseline, "compact": str(root/"best.pt")}
    frozen = {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in checkpoints.items()}
    freeze_path = root/"frozen-checkpoints.json"
    if freeze_path.exists() and json.loads(freeze_path.read_text()) != frozen:
        raise ValueError("保留评估开始后检查点发生变化")
    write_json(freeze_path, frozen)
    reports = {}
    for name, checkpoint in checkpoints.items():
        for subset in ("heldout", "diagnostic"):
            output = root/(name+"-"+subset)
            if not (output/"report.json").exists():
                print("开始完整生成评估 "+name+"-"+subset, flush=True)
                execute(["-m", "training.benchmark", "--data", str(data/(subset+".jsonl")), "--checkpoint", checkpoint,
                    "--output", str(output), "--split", "test", "--limit", "100", "--candidates", "8", "--seed", "41"],
                    root/(name+"-"+subset+".log"))
            report = json.loads((output/"report.json").read_text())
            if report["checkpoint_sha256"] != frozen[name]:
                raise ValueError("评估与检查点不一致")
            # 通用评估器的默认范围说明在这里按本轮真实来源补充。
            report["scope"] = "强充能新几何组合、保留专家来源迁移和旧推驱分项报告" if subset == "heldout" else "训练来源拉驱任务的构造诊断，不是独立泛化"
            write_json(output/"report.json", report)
            reports[name+"-"+subset] = report
    current = reports["compact-heldout"]["families"]["strong_compact"]["successes"]
    previous = reports["baseline-heldout"]["families"]["strong_compact"]["successes"]
    rows = read_examples(root/"compact-heldout/results.jsonl")
    counts = {len(r["task"]["targets"]) for r in rows if r["family"] == "strong_compact" and r["accepted"]}
    report = {"experiment_completed": True, "strong_course_gate_passed": current >= 10 and current > previous and {4, 5} <= counts,
              "stage3_complete": False, "reports": reports,
              "note": "首轮联合课程结果；强充能、回拉、多时序和混合材料的运行证据另行分析，不自动进入阶段四。"}
    write_json(root/"stage3-result.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "reports"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

"""回传后分析成功轨迹，将代表结构保存到服务器网页。"""

import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
from urllib.request import Request, urlopen

from ..serialization import digest, write_json
from .mechanisms import analyze


def main():
    parser = argparse.ArgumentParser(description="第三阶段结果取证和网页交付")
    parser.add_argument("--runs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    runs, output = Path(args.runs), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    evidence, candidates, breakdown = {}, {}, {}
    for arm in ("baseline", "compact", "last"):
        for subset in ("heldout", "diagnostic", "five-target"):
            key = arm+"-"+subset
            directory = runs/key
            if not (directory/"results.jsonl").exists():
                continue
            rows = [json.loads(s) for s in (directory/"results.jsonl").read_text().splitlines()]
            summaries, successful = [], []
            groups = defaultdict(lambda: {"tasks": 0, "successes": 0, "strong": 0, "pull": 0, "mixed_separation": 0})
            for row in rows:
                family = row["family"]
                groups[family]["tasks"] += 1
                if not row["accepted"]:
                    continue
                groups[family]["successes"] += 1
                proposal = row["proposals"][row["first_success_candidate"]-1]
                with gzip.open(directory/(row["task_id"]+".trace.json.gz"), "rt") as handle:
                    proof = json.load(handle)
                observed = analyze(proof["trace"])
                groups[family]["strong"] += bool(observed["strong_power_only_pairs"])
                groups[family]["pull"] += bool(observed["nonempty_pull_operations"])
                groups[family]["mixed_separation"] += bool(observed["mixed_boundaries_separated_in_motion"])
                zs = [b["position"]["z"] for b in proposal["blocks"]]
                item = {"task_id": row["task_id"], "family": family, "group": row["group"], "task": row["task"],
                        "actual_depth": max(zs)-min(zs)+1, "mechanisms": observed,
                        "target_ticks": proof["rounds"][0]["ticks"], "proposal": proposal}
                successful.append(item)
                summaries.append({k: v for k, v in item.items() if k != "proposal"})
            evidence[key] = summaries
            candidates[key] = successful
            breakdown[key] = dict(groups)
    write_json(output/"mechanism-evidence.json", {"breakdown": breakdown, "successes": evidence})
    chosen = []
    for count in (4, 5, 7):
        eligible = [r for r in [*candidates["compact-heldout"], *candidates.get("compact-five-target", [])] if r["family"] == "strong_compact"
                    and len(r["task"]["targets"]) == count and r["mechanisms"]["strong_power_only_pairs"]]
        if eligible:
            chosen.append((f"阶段3·{count}目标两格强充能", eligible[0], "训练后补充的未见几何评估" if count == 5 else "新几何保留需求"))
    independent = [r for r in candidates["compact-heldout"] if r["family"] == "expert_compact"
                   and r["mechanisms"]["nonempty_pull_operations"]]
    if independent:
        chosen.append(("阶段3·源外拉驱", independent[0], "保留专家来源"))
    accompanying = [r for r in candidates["compact-heldout"] if r["family"] == "strong_compact"
                    and r["mechanisms"]["nonempty_pull_operations"]]
    if accompanying:
        chosen.append(("阶段3·强充能伴随回拉", accompanying[0], "强充能保留需求出现非空回拉；未证明回拉对压缩或时序必不可少"))
    diagnostic = [r for r in candidates["compact-diagnostic"] if r["mechanisms"]["nonempty_pull_operations"]]
    diagnostic_scope = "训练来源构造诊断，不是独立泛化"
    if not diagnostic:
        diagnostic = [r for r in candidates.get("last-diagnostic", []) if r["mechanisms"]["nonempty_pull_operations"]]
        diagnostic_scope = "第6000步末步检查点的训练来源诊断；不是正式选模结果或独立泛化"
    if diagnostic:
        diagnostic.sort(key=lambda r: (bool(r["mechanisms"]["mixed_boundaries_separated_in_motion"]), len(r["task"]["targets"])), reverse=True)
        chosen.append(("阶段3·同源拉驱诊断", diagnostic[0], diagnostic_scope))
    scenes, exhibits = [], []
    for name, row, scope in chosen:
        proposal, task = row["proposal"], row["task"]
        loads = [{"position": dict(x=t["x"], y=t["y"], z=t["z"]+i),
                  "block": {"kind": "iron_block", "facing": "positive_z"}}
                 for t in task["targets"] for i in range(10)]
        piston = {"position": {**proposal["push"], "z": proposal["push"]["z"]-1},
                  "block": {"kind": "piston", "facing": "positive_z"}}
        for suffix, blocks in (("本体", proposal["blocks"]), ("十负载装配", [*proposal["blocks"], *loads, piston])):
            scene = {"id": digest(["stage3_exhibit", name, blocks]), "name": name+"·"+suffix, "blocks": blocks}
            scenes.append(scene)
            write_json(output/(scene["name"]+".scene.json"), scene)
        exhibits.append({"name": name, "scope": scope, **row})
    result = {"exhibits": exhibits, "breakdown": breakdown}
    if args.publish and scenes:
        request = Request("http://127.0.0.1:8010/api/datasets/scenes/migrate",
            data=json.dumps({"items": scenes}, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=60) as response:
            saved = json.load(response)
        result["published"] = [{k: row[k] for k in ("name", "id", "revision")} for row in saved["items"]]
    write_json(output/"showcase.json", result)
    print(json.dumps({"分项结果": breakdown, "展示": [r["name"] for r in exhibits]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

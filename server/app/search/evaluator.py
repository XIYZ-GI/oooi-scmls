import json
import time

import mcscai_engine

from app.services.target_load import TargetLoadTracker, build_target_loads


PROTOCOL = "search_translation_load10_v1"


def evaluate(seed, proposal, rounds):
    """只评估搜索候选；原始样本直接使用已保存的标注结果。"""
    started = time.monotonic()
    simulator = mcscai_engine.Simulator()

    def apply(command):
        return json.loads(simulator.apply(json.dumps(command)))

    reference = seed["reference"]["targets"]
    expected = {(p["x"], p["y"], p["z"]): p["order"] for p in reference}
    request = seed["request"]
    targets = [dict(p) for p in request["targets"]]
    blocks = proposal["blocks"]
    push = proposal["push"]
    actuator = {**push, "z": push["z"] - 1}
    power = {**push, "z": push["z"] - 2}
    snapshot = apply({"type": "replace_world", "blocks": [*blocks, *build_target_loads(targets),
        {"position": actuator, "block": {"kind": "piston", "facing": "positive_z"}},
        {"position": power, "block": {"kind": "redstone_block", "facing": "positive_z"}}]})
    lookup = {tuple(b["position"][a] for a in ("x", "y", "z")): b["id"] for b in snapshot["blocks"]}
    members = [(lookup[tuple(b["position"][a] for a in ("x", "y", "z"))], b["position"]) for b in blocks]
    result = {"accepted": False, "load_pass": False, "rounds": [], "reason": "",
              "protocol": PROTOCOL, "engineVersion": mcscai_engine.__version__, "loadBlocks": 10,
              "maxTicks": request["max_ticks"], "requiredRounds": rounds}

    for cycle in range(rounds):
        tracker = TargetLoadTracker(snapshot, targets)
        settled = 0
        finished = False
        timing_ok = False
        reason = ""
        for tick in range(1, request["max_ticks"] + 1):
            if time.monotonic() - started > 20:
                reason = "候选计算超过 20 秒上限"
                break
            snapshot = apply({"type": "step", "ticks": 1})
            reason = tracker.observe(snapshot, tick)
            if reason:
                break
            if tick == 4:
                snapshot = apply({"type": "remove_block", "position": power})
            if tracker.complete:
                groups = {value: i + 1 for i, value in enumerate(sorted({p["tick"] for p in tracker.results}))}
                timing_ok = all(groups[p["tick"]] == expected[(p["x"], p["y"], p["z"] - cycle)] for p in tracker.results)
                if not timing_ok:
                    reason = "目标完成顺序或同时完成分组发生变化"
                    break
                if cycle == 0:
                    result["load_pass"] = True
                actual = {b["id"]: b for b in snapshot["blocks"]}
                translated = all(block_id in actual and actual[block_id]["position"] == {**position, "z": position["z"] + cycle + 1}
                                 for block_id, position in members)
                idle = not snapshot["motions"] and not snapshot["arms"] and all(
                    (not b.get("piston_phase") or b["piston_phase"]["phase"] == "retracted") and
                    (not b.get("observer_phase") or b["observer_phase"]["phase"] == "idle")
                    for b in snapshot["blocks"])
                settled = settled + 1 if translated and idle and tick > 4 else 0
                if settled >= 4:
                    finished = True
                    break
        result["rounds"].append({"round": cycle + 1, "ticks": tick, "targets": tracker.results,
                                 "timing_pass": timing_ok, "translation_pass": finished})
        if not finished:
            result["reason"] = reason or ("负载已完成，但移动线尚未整体前进一格并恢复静止" if tracker.complete
                                         else "时限内未能推动所有目标的十块负载")
            return result
        if cycle + 1 < rounds:
            apply({"type": "remove_block", "position": actuator})
            actuator = {**actuator, "z": actuator["z"] + 1}
            power = {**power, "z": power["z"] + 1}
            occupied = {tuple(b["position"][a] for a in ("x", "y", "z")) for b in snapshot["blocks"]
                        if b["position"] != {**actuator, "z": actuator["z"] - 1}}
            if any(tuple(p[a] for a in ("x", "y", "z")) in occupied for p in (actuator, power)):
                result["reason"] = "下一轮外部推动装置位置被结构占用"
                return result
            apply({"type": "set_block", "position": actuator, "block": {"kind": "piston", "facing": "positive_z"}})
            snapshot = apply({"type": "set_block", "position": power, "block": {"kind": "redstone_block", "facing": "positive_z"}})
            targets = [{**p, "z": p["z"] + 1} for p in targets]
    result["accepted"] = True
    return result

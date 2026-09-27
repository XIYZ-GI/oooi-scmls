"""按需求判定候选结构：三轮连续推动，每列目标推过十块负载。

判定口径与网页推理页完全一致，不额外要求每个活塞都必须激活过。整线平移、方块
是否随行等只作为诊断字段记录，不参与通过与否。
"""

import json
import time

import mcscai_engine

from .constants import AXES, PROTOCOL, STATE_IDS
from .domain_rules import proposal_issues, snapshot_issues
from .domain_rules.constants import RULE, REASON

# 无时限任务的兜底上限：正常机器几十刻就完成，只有完全不动或反复回拉才会跑这么远。
SAFETY_TICKS = 2000
# 无时限任务里连续这么多刻没有任何负载前进就直接判定失败，避免坏候选拖满安全上限。
STALL_TICKS = 400
# 轮与轮之间的固定间隔：上一轮判定结束后先空跑这么多刻，再进行下一轮，
# 让机体在下一轮推动前稳定下来；间隔期间外部推动器仍停在原位（已回缩且无供电）。
ROUND_GAP_TICKS = 10


def idle_snapshot(snapshot):
    """没有信号源、待执行动作或运动时，后续空刻不会产生状态变化。"""
    return not snapshot['motions'] and not snapshot['arms'] and all(
        block['kind'] != 'redstone_block' and not block['powered'] and not block['strongly_powered']
        and (block.get('observer_phase') or {}).get('phase', 'idle') == 'idle'
        and (block.get('piston_phase') or {}).get('phase', 'retracted') == 'retracted'
        for block in snapshot['blocks'])


def evaluate(task, proposal, capture=False, idle_batch=False):
    started = time.monotonic()
    result = {"accepted": False, "protocol": PROTOCOL, "engine_version": mcscai_engine.__version__,
              "rounds": [], "reason": "", "load_blocks": 10, "simulator_started": False, "simulated_ticks": 0,
              "design_rule": RULE}
    trace = []
    engine = mcscai_engine.Simulator()
    native_apply = getattr(engine, 'apply_native', None)
    last_sequence = 0

    def apply(command):
        nonlocal last_sequence
        encoded = json.dumps(command, separators=(",", ":"))
        snapshot = native_apply(encoded) if native_apply else json.loads(engine.apply(encoded))
        issues = snapshot_issues(snapshot)
        if issues:
            result['design_issues'] = issues
            raise ValueError(REASON)
        if command["type"] == "step":
            result["simulated_ticks"] += command["ticks"]
        if capture:
            frame = {k: v for k, v in snapshot.items() if k != "events"}
            frame["events"] = [e for e in snapshot["events"] if e["sequence"] > last_sequence]
            last_sequence = max((e["sequence"] for e in snapshot["events"]), default=last_sequence)
            trace.append({"command": command, "snapshot": frame})
        return snapshot

    def fail(reason):
        result["reason"] = reason
        result["seconds"] = time.monotonic() - started
        if capture:
            result["trace"] = trace
        return result

    blocks, push = proposal["blocks"], proposal["push"]
    occupied = {tuple(b["position"][a] for a in AXES) for b in blocks}
    if not blocks or len(occupied) != len(blocks):
        return fail("空结构或重复方块位置")
    if any(not (0 <= x < task["width"] and 0 <= y < task["height"] and -task["depth"]-1 <= z <= -2)
           for x, y, z in occupied):
        return fail("结构超出初始设计空间")
    if any((b["block"]["kind"], b["block"].get("facing", "positive_z")) not in STATE_IDS for b in blocks):
        return fail("非法方块或方向")
    if tuple(push[a] for a in AXES) not in occupied or any(
            x == push["x"] and y == push["y"] and z < push["z"] for x, y, z in occupied):
        return fail("推动点不是所在列后方可接触的方块")
    issues = proposal_issues(proposal)
    if issues:
        result['design_issues'] = issues
        return fail(REASON)
    loads = [{"position": {"x": t["x"], "y": t["y"], "z": t["z"] + i},
              "block": {"kind": "iron_block", "facing": "positive_z"}}
             for t in task["targets"] for i in range(10)]
    actuator = {**push, "z": push["z"]-1}
    power = {**push, "z": push["z"]-2}
    world = [*blocks, *loads, {"position": actuator, "block": {"kind": "piston", "facing": "positive_z"}},
             {"position": power, "block": {"kind": "redstone_block", "facing": "positive_z"}}]
    if len({tuple(b["position"][a] for a in AXES) for b in world}) != len(world):
        return fail("初始结构、负载或外部推动装置重叠")
    try:
        result["simulator_started"] = True
        snapshot = apply({"type": "replace_world", "blocks": world})
        ids = {tuple(b["position"][a] for a in AXES): b["id"] for b in snapshot["blocks"]}
        members = [(ids[tuple(b["position"][a] for a in AXES)], b["position"]) for b in blocks]
        load_members = [[(ids[(t["x"], t["y"], t["z"]+i)], t["z"]+i) for i in range(10)] for t in task["targets"]]
        # max_ticks 为 0 表示无时限：每轮跑到全部目标推完就结束，只用安全上限兜底。
        unlimited = not task["max_ticks"]
        limit = SAFETY_TICKS if unlimited else task["max_ticks"]
        for cycle in range(task["rounds"]):
            ticks = [None] * len(task["targets"])
            moved = set()
            progress_count, progress_tick = 0, 0
            tick = 0
            while tick < limit:
                # 只合并已完成目标后的静止段；引擎仍执行每一刻，保留周期端点快照。
                steps = min(limit-tick, 1000) if (idle_batch and not unlimited and tick >= 4
                        and all(t is not None for t in ticks) and idle_snapshot(snapshot)) else 1
                tick += steps
                snapshot = apply({"type": "step", "ticks": steps})
                actual = {b["id"]: b for b in snapshot["blocks"]}
                for i, (target, group) in enumerate(zip(task["targets"], load_members)):
                    complete = True
                    for block_id, start_z in group:
                        p = actual.get(block_id, {}).get("position", {})
                        z = p.get("z")
                        if p.get("x") != target["x"] or p.get("y") != target["y"] or z not in (start_z+cycle, start_z+cycle+1):
                            return fail("负载消失、侧移或超出一格")
                        if z == start_z+cycle+1:
                            moved.add(block_id)
                        else:
                            if block_id in moved:
                                return fail("负载被回拉")
                            complete = False
                    if complete and ticks[i] is None:
                        ticks[i] = tick
                if unlimited:
                    if len(moved) > progress_count:
                        progress_count, progress_tick = len(moved), tick
                    elif tick - progress_tick > STALL_TICKS:
                        return fail("连续多刻没有任何负载前进")
                    if all(t is not None for t in ticks):
                        # 本轮目标全部推完，本轮判定到此为止，后面不再检查。
                        break
                if tick == 4:
                    snapshot = apply({"type": "remove_block", "position": power})
                if time.monotonic()-started > 30:
                    return fail("完整候选模拟达到三十秒上限")
            if any(t is None for t in ticks):
                return fail("安全上限内未完成全部目标的十块负载" if unlimited
                            else "时限内未完成全部目标的十块负载")
            ranks = {t: i+1 for i, t in enumerate(sorted(set(ticks)))}
            if any(ranks[tick] != target["order"] for tick, target in zip(ticks, task["targets"])):
                # 每个目标的十块负载只要都在前进，就说明机器确实在推动负载；
                # 此时若仅时序分组不合格，记作半通过，便于优先展示。
                advanced = {i for i, group in enumerate(load_members)
                            if any(block_id in moved for block_id, _ in group)}
                reason = "目标先后顺序或同刻分组不符合需求"
                if len(advanced) == len(task["targets"]):
                    result["partial"] = True
                    result["partial_reason"] = reason
                    result.setdefault("partial_rounds", []).append(cycle+1)
                return fail(reason)
            actual = {b["id"]: b for b in snapshot["blocks"]}
            # 判定标准是连续运行与按需求时序推完全部十块负载；个别方块未随行只作为诊断，
            # 不再单独判失败。整线是否平移仍记录在 rounds 里。
            stayed = [dict(p) for i, p in members
                      if actual.get(i, {}).get("position") != {**p, "z": p["z"]+cycle+1}]
            if stayed:
                result.setdefault("body_diagnostics", []).append(
                    dict(round=cycle+1, moved=len(members)-len(stayed), total=len(members), unmoved=stayed))
            # 只要求外部触发器能安全搬到下一轮；不强制整线所有观察者静止。
            external = next((b for b in snapshot["blocks"] if b["position"] == actuator), None)
            # 该位置被别的方块占住时 piston_phase 可能是 None，按“未回缩”处理而不是抛异常。
            if not external or (external.get("piston_phase") or {}).get("phase") != "retracted":
                return fail("外部推动器在周期末未回缩")
            result["rounds"].append({"round": cycle+1, "ticks": ticks,
                                     "period": task["max_ticks"] or max(t for t in ticks),
                                     "translation": not stayed})
            if cycle+1 < task["rounds"]:
                if ROUND_GAP_TICKS:
                    snapshot = apply({"type": "step", "ticks": ROUND_GAP_TICKS})
                snapshot = apply({"type": "remove_block", "position": actuator})
                actuator = {**actuator, "z": actuator["z"]+1}
                power = {**power, "z": power["z"]+1}
                blocked = {tuple(b["position"][a] for a in AXES) for b in snapshot["blocks"]}
                blocked.update(tuple(a["position"][k] for k in AXES) for a in snapshot["arms"])
                if any(tuple(p[a] for a in AXES) in blocked for p in (actuator, power)):
                    return fail("下一轮外部推动装置位置被占用")
                apply({"type": "set_block", "position": actuator, "block": {"kind": "piston", "facing": "positive_z"}})
                snapshot = apply({"type": "set_block", "position": power, "block": {"kind": "redstone_block", "facing": "positive_z"}})
    except (ValueError, KeyError) as error:
        return fail(REASON if result.get('design_issues') else f"模拟输入不合法：{error}")
    result["accepted"] = True
    result["seconds"] = time.monotonic()-started
    if capture:
        result["trace"] = trace
    return result

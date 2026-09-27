import json
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from typing import Any

import mcscai_engine
from app.models.load_protocol import TARGET_LOAD_BLOCKS, LOAD_TIMING_PROTOCOL
from app.models.push_point import resolve_push_point
from .target_load import build_target_loads, TargetLoadTracker


PULSE_TICKS = 4
MAX_SECONDS = 20
timing_executor = ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn"))


def calculate_label_timing(request: dict[str, Any], recorder=None) -> dict[str, Any]:
    """所有目标同时施加十块负载，逐块跟踪前进一格的完成刻。"""
    started = time.monotonic()
    engine = mcscai_engine.Simulator()

    def apply(command: dict[str, Any]) -> dict[str, Any]:
        return json.loads(engine.apply(json.dumps(command, separators=(",", ":"))))

    blocks = list(request["blocks"])
    push = resolve_push_point([(item["position"]["x"], item["position"]["y"], item["position"]["z"]) for item in blocks], request["push_point"])
    actuator = {**push, "z": push["z"] - 1}
    power = {**push, "z": push["z"] - 2}
    blocks.extend(build_target_loads(request["targets"]))
    blocks.extend([
        {"position": actuator, "block": {"kind": "piston", "facing": "positive_z"}},
        {"position": power, "block": {"kind": "redstone_block", "facing": "positive_z"}},
    ])
    snapshot = apply({"type": "replace_world", "blocks": blocks})
    tracker = TargetLoadTracker(snapshot, request["targets"])
    if recorder is not None:
        recorder.append(snapshot, tracker)
    results = tracker.results
    reason = ""
    elapsed_ticks = 0
    seconds_limit = 60 if recorder is not None else MAX_SECONDS

    for tick in range(1, request["max_ticks"] + 1):
        if time.monotonic() - started > seconds_limit:
            reason = f"本次计算达到 {seconds_limit} 秒上限，已保留已测得的目标时间"
            break
        snapshot = apply({"type": "step", "ticks": 1})
        elapsed_ticks = tick
        reason = tracker.observe(snapshot, tick)
        finished = not reason and tracker.complete
        if not finished and tick == PULSE_TICKS:
            snapshot = apply({"type": "remove_block", "position": power})
        if recorder is not None:
            recorder.append(snapshot, tracker)
        if finished or tick == request["max_ticks"]:
            break

    success = not reason and tracker.complete
    if success:
        groups = {tick: index + 1 for index, tick in enumerate(sorted({point["tick"] for point in results}))}
        for point in results:
            point["order"] = groups[point["tick"]]
    else:
        missing = sum(point["tick"] is None or bool(point["error"]) for point in results)
        reason = reason or f"在 {request['max_ticks']} 游戏刻内，有 {missing}/{len(results)} 个目标未能将整列 {TARGET_LOAD_BLOCKS} 个负载方块全部推动一格"
    for point in results:
        point["failed"] = point["tick"] is None or bool(point["error"])
    result = {
        "status": "success" if success else "failed", "reason": reason,
        "targets": results, "simulatedTicks": elapsed_ticks, "maxTicks": request["max_ticks"],
        "pulseTicks": PULSE_TICKS, "protocol": LOAD_TIMING_PROTOCOL, "loadBlocks": TARGET_LOAD_BLOCKS,
        "engineVersion": mcscai_engine.__version__,
    }
    if recorder is not None:
        result["replay"] = recorder.finish(result)
    return result

"""从真实模拟状态提取回拉、强充能供电及混合材料运动证据。"""


VECTORS = {"positive_x": (1, 0, 0), "negative_x": (-1, 0, 0),
           "positive_y": (0, 1, 0), "negative_y": (0, -1, 0),
           "positive_z": (0, 0, 1), "negative_z": (0, 0, -1)}


def analyze(trace):
    pulls, relays, separated, boundaries = set(), set(), set(), set()
    for frame in trace:
        s = frame["snapshot"]
        blocks = {tuple(b["position"][a] for a in ("x", "y", "z")): b for b in s["blocks"]}
        moving = {b["block_id"]: (m["piston_id"], m["started_at"]) for m in s["motions"] for b in m["blocks"]}
        for motion in s["motions"]:
            if motion["kind"] == "pull" and motion["blocks"]:
                pulls.add((motion["piston_id"], motion["started_at"], len(motion["blocks"])))
        for pos, b in blocks.items():
            if b["kind"] in ("slime_block", "honey_block"):
                for v in VECTORS.values():
                    other = blocks.get(tuple(x+d for x, d in zip(pos, v)))
                    if other and {b["kind"], other["kind"]} == {"slime_block", "honey_block"}:
                        pair = tuple(sorted((b["id"], other["id"])))
                        boundaries.add(pair)
                        if moving.get(b["id"]) != moving.get(other["id"]):
                            separated.add(pair)
            if b["kind"] not in ("piston", "sticky_piston") or not b["powered"]:
                continue
            strong_inputs, direct = [], False
            for direction, v in VECTORS.items():
                if direction == b["facing"]:
                    continue
                other_pos = tuple(x+d for x, d in zip(pos, v))
                other = blocks.get(other_pos)
                if not other:
                    continue
                if other["strongly_powered"]:
                    strong_inputs.append(other["id"])
                if other["kind"] == "redstone_block":
                    direct = True
                if other["kind"] == "observer" and (other.get("observer_phase") or {}).get("phase") == "pulsing":
                    target = tuple(x+d for x, d in zip(other_pos, VECTORS[other["facing"]]))
                    direct |= target == pos
            # 只记录没有直接观察者或红石块来源时的强充能转发证据。
            if strong_inputs and not direct:
                relays.update((b["id"], source) for source in strong_inputs)
    return {"nonempty_pull_operations": len(pulls), "pull_operations": sorted(pulls),
            "strong_power_only_pairs": sorted(relays), "mixed_material_boundaries": sorted(boundaries),
            "mixed_boundaries_separated_in_motion": sorted(separated),
            "note": "强充能转发按模拟器现有供电规则对快照取证；混合材料分离运动是轨迹证据，不等于证明该界面对压缩必不可少。"}

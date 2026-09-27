from app.models.load_protocol import TARGET_LOAD_BLOCKS


def build_target_loads(targets):
    """每个目标的首个铁块从自身初始位置起，沿前进方向连续放置十块。"""
    return [
        {"position": {"x": point["x"], "y": point["y"], "z": point.get("z", 0) + offset},
         "block": {"kind": "iron_block", "facing": "positive_z"}}
        for point in targets for offset in range(TARGET_LOAD_BLOCKS)
    ]


class TargetLoadTracker:
    def __init__(self, snapshot, targets):
        ids = {tuple(block["position"][axis] for axis in ("x", "y", "z")): block["id"] for block in snapshot["blocks"]}
        self.results = [{**point, "z": point.get("z", 0), "tick": None, "order": None, "movedBlocks": 0, "error": ""} for point in targets]
        self.members = [
            [(ids[(point["x"], point["y"], point["z"] + offset)], point["z"] + offset) for offset in range(TARGET_LOAD_BLOCKS)]
            for point in self.results
        ]
        self.moved_ids = set()

    def observe(self, snapshot, tick):
        locations = {block["id"]: block["position"] for block in snapshot["blocks"]}
        reason = ""
        for point, members in zip(self.results, self.members):
            moved = 0
            for block_id, start_z in members:
                position = locations.get(block_id)
                if position is None or position["x"] != point["x"] or position["y"] != point["y"] or position["z"] not in (start_z, start_z + 1):
                    point["error"] = point["error"] or f"目标 ({point['x']}, {point['y']}) 的负载出现侧移、消失或超出一格的位移"
                    continue
                if position["z"] == start_z + 1:
                    moved += 1
                    self.moved_ids.add(block_id)
                elif block_id in self.moved_ids:
                    point["error"] = point["error"] or f"目标 ({point['x']}, {point['y']}) 的负载在全部目标完成前被拉回"
            point["movedBlocks"] = moved
            if moved == TARGET_LOAD_BLOCKS and point["tick"] is None:
                point["tick"] = tick
            reason = reason or point["error"]
        return reason

    @property
    def complete(self):
        return all(point["tick"] is not None for point in self.results)

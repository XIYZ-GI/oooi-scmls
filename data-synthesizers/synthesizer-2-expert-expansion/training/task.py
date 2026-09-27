"""独立推理入口的需求校验，避免空任务或零轮次被误判为成功。"""


def validate_task(task):
    if not isinstance(task, dict):
        raise ValueError("需求必须是 JSON 对象")
    for field in ("width", "height", "depth"):
        if type(task.get(field)) is not int or not 1 <= task[field] <= 32:
            raise ValueError("宽、高、厚度必须为一至三十二之间的整数")
    if task["width"]*task["height"]*task["depth"] > 512:
        raise ValueError("阶段一推理入口的初始空间最多五百一十二格")
    # max_ticks 允许为 0：十二维需求模型不读时限，判定按“推完即结束”执行，只用安全上限兜底。
    if type(task.get("max_ticks")) is not int or not (task["max_ticks"] == 0 or 8 <= task["max_ticks"] <= 2000):
        raise ValueError("每轮刻数必须为 0（无时限）或 8 至 2000 之间的整数")
    if type(task.get("rounds")) is not int or not 2 <= task["rounds"] <= 20:
        raise ValueError("连续轮数必须为 2 至 20 之间的整数")
    if task.get("load_blocks") != 10:
        raise ValueError("当前协议要求每个目标固定十块铁块负载")
    targets = task.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 32:
        raise ValueError("目标列表不能为空且最多三十二个点")
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("目标点必须是对象")
        for key, lower, upper in (("x", 0, task["width"]-1), ("y", 0, task["height"]-1), ("z", -64, 64), ("order", 1, 32)):
            if type(target.get(key)) is not int or not lower <= target[key] <= upper:
                raise ValueError(f"目标点的 {key} 超出范围或不是整数")
    if len({(t["x"], t["y"]) for t in targets}) != len(targets):
        raise ValueError("每一截面坐标只能有一个目标点")
    orders = {t["order"] for t in targets}
    if orders != set(range(1, max(orders)+1)):
        raise ValueError("目标时序组必须从一开始连续编号")
    return task

"""按模型声明的需求口径归一化判定参数。

十二维需求模型不把每轮刻数、连续轮数、每目标负载数读进网络，这三个值只决定验收标准。
为了让“隐藏输入框”等于“这些值不再起作用”，凡是模型声明不读的字段一律回到固定协议值，
避免历史草稿里残留的 200 刻、10 轮继续影响判定。
"""

# 模型不读运行协议时，判定按固定协议执行：连续三轮、每目标十块负载、每轮不设刻数上限。
FIXED = dict(max_ticks=0, rounds=3, load_blocks=10)
# 读取每轮刻数的旧版本不认“无时限”，草稿里若是 0 就还原成协议默认值。
DEFAULT_TICKS = 48


def fixed_protocol(task, entry):
    """把模型不读的运行协议字段固定成协议值；旧版本权重没有 conditioning，保持不变。"""
    conditioning = (entry or {}).get('conditioning') or {}
    value = dict(task)
    for field, fixed in FIXED.items():
        if conditioning.get(field) is False:
            value[field] = fixed
    if conditioning.get('max_ticks', True) and not value.get('max_ticks'):
        value['max_ticks'] = DEFAULT_TICKS
    return value

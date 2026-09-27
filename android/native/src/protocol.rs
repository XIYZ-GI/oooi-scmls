//! 与服务器端 `training/constants.py`、`training/evaluator.py` 对齐的协议常量。
//!
//! 这里的每个数值都必须与 Python 侧一致，否则安卓端与服务器的判定结果会分叉。

/// 判定协议标识，写入结果供上层核对。
pub const PROTOCOL: &str = "generation_fixed_cycle_load10_v1";

/// 领域规则标识。
pub const RULE: &str = "piston_observer_detection_face_v1";

/// 领域规则的统一失败原因。
pub const RULE_REASON: &str = "设计禁忌：活塞直接朝观察者侦测端推动";

/// 无时限任务的兜底上限：正常机器几十刻就完成，只有完全不动或反复回拉才会跑这么远。
pub const SAFETY_TICKS: u64 = 2000;

/// 无时限任务里连续这么多刻没有任何负载前进就直接判定失败。
pub const STALL_TICKS: u64 = 400;

/// 轮与轮之间的固定间隔，让机体在下一轮推动前稳定下来。
pub const ROUND_GAP_TICKS: u32 = 10;

/// 当前协议要求每个目标固定十块铁块负载。
pub const LOAD_BLOCKS: usize = 10;

/// 单个候选的实际时间上限（秒）。
pub const TIME_LIMIT_SECONDS: f64 = 30.0;

/// 三个坐标轴的字段名顺序，与 Python 侧 `AXES` 一致。
pub const AXES: [&str; 3] = ["x", "y", "z"];

/// 方块状态词表，索引即模型 token。
///
/// 与 `training/constants.py` 的 `STATES` 逐项对应，共 25 项：
/// 空气、六种无朝向方块、活塞六向、粘性活塞六向、观察者六向。
/// **顺序不可改动**，它决定模型输出的解码结果；`BOS` 等于该表长度。
pub const STATES: [(&str, &str); 25] = [
    ("air", "positive_z"),
    ("slime_block", "positive_z"),
    ("honey_block", "positive_z"),
    ("redstone_block", "positive_z"),
    ("iron_block", "positive_z"),
    ("light_blue_glazed_terracotta", "positive_z"),
    ("glass", "positive_z"),
    ("piston", "positive_x"),
    ("piston", "negative_x"),
    ("piston", "positive_y"),
    ("piston", "negative_y"),
    ("piston", "positive_z"),
    ("piston", "negative_z"),
    ("sticky_piston", "positive_x"),
    ("sticky_piston", "negative_x"),
    ("sticky_piston", "positive_y"),
    ("sticky_piston", "negative_y"),
    ("sticky_piston", "positive_z"),
    ("sticky_piston", "negative_z"),
    ("observer", "positive_x"),
    ("observer", "negative_x"),
    ("observer", "positive_y"),
    ("observer", "negative_y"),
    ("observer", "positive_z"),
    ("observer", "negative_z"),
];

/// 序列起止标记，等于有效状态总数。
pub const BOS: usize = STATES.len();

/// 需要读取朝向的方块种类；其余方块朝向固定为 `positive_z`。
pub const DIRECTIONAL_KINDS: [&str; 3] = ["piston", "sticky_piston", "observer"];

/// 方块的六种朝向名称，与引擎的 `Direction` 序列化名一致。
pub const DIRECTIONS: [&str; 6] = [
    "positive_x",
    "negative_x",
    "positive_y",
    "negative_y",
    "positive_z",
    "negative_z",
];

/// 判断某个方块种类是否需要读取朝向。
pub fn is_directional(kind: &str) -> bool {
    DIRECTIONAL_KINDS.contains(&kind)
}

/// 把 `(方块种类, 朝向)` 换成模型 token；未知组合返回 `None`。
pub fn state_id(kind: &str, facing: &str) -> Option<usize> {
    let facing = if is_directional(kind) { facing } else { "positive_z" };
    STATES.iter().position(|s| s.0 == kind && s.1 == facing)
}

/// 把模型 token 换回 `(方块种类, 朝向)`；越界或 0（空气）返回 `None`。
pub fn state_of(token: usize) -> Option<(&'static str, &'static str)> {
    // token 0 是空气，解码结构时跳过。
    if token == 0 || token >= STATES.len() {
        return None;
    }
    Some(STATES[token])
}

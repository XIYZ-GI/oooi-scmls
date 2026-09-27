//! 需求校验，对应 `training/task.py`。
//!
//! 校验文案与 Python 侧逐字一致，便于两边失败原因直接比对。

use serde::{Deserialize, Serialize};

/// 一个目标点。
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Target {
    pub x: i32,
    pub y: i32,
    pub z: i32,
    pub order: i32,
}

/// 一次生成需求。
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Task {
    pub width: i32,
    pub height: i32,
    pub depth: i32,
    pub max_ticks: i32,
    pub rounds: i32,
    pub load_blocks: i32,
    pub targets: Vec<Target>,
}

impl Task {
    /// 单列坐标；与 Python 侧 `[(t['x'], t['y'])]` 的作用一致。
    pub fn columns(&self) -> Vec<(i32, i32)> {
        self.targets.iter().map(|t| (t.x, t.y)).collect()
    }
}

/// 校验需求，失败时返回与 Python 侧一致的中文原因。
pub fn validate(task: &Task) -> Result<(), String> {
    for (value, name) in [
        (task.width, "宽"),
        (task.height, "高"),
        (task.depth, "厚度"),
    ] {
        if !(1..=32).contains(&value) {
            let _ = name;
            return Err("宽、高、厚度必须为一至三十二之间的整数".into());
        }
    }
    let volume = task.width as i64 * task.height as i64 * task.depth as i64;
    if volume > 512 {
        return Err("阶段一推理入口的初始空间最多五百一十二格".into());
    }
    // max_ticks 允许为 0：十二维需求模型不读时限，判定按“推完即结束”执行，只用安全上限兜底。
    if !(task.max_ticks == 0 || (8..=2000).contains(&task.max_ticks)) {
        return Err("每轮刻数必须为 0（无时限）或 8 至 2000 之间的整数".into());
    }
    if !(2..=20).contains(&task.rounds) {
        return Err("连续轮数必须为 2 至 20 之间的整数".into());
    }
    if task.load_blocks != 10 {
        return Err("当前协议要求每个目标固定十块铁块负载".into());
    }
    if task.targets.is_empty() || task.targets.len() > 32 {
        return Err("目标列表不能为空且最多三十二个点".into());
    }
    for target in &task.targets {
        if !(0..task.width).contains(&target.x) {
            return Err("目标点的 x 超出范围或不是整数".into());
        }
        if !(0..task.height).contains(&target.y) {
            return Err("目标点的 y 超出范围或不是整数".into());
        }
        if !(-64..=64).contains(&target.z) {
            return Err("目标点的 z 超出范围或不是整数".into());
        }
        if !(1..=32).contains(&target.order) {
            return Err("目标点的 order 超出范围或不是整数".into());
        }
    }
    // 每一截面坐标只能有一个目标点。
    let mut columns: Vec<(i32, i32)> = task.columns();
    columns.sort();
    let unique = {
        let mut copy = columns.clone();
        copy.dedup();
        copy.len()
    };
    if unique != task.targets.len() {
        return Err("每一截面坐标只能有一个目标点".into());
    }
    // 目标时序组必须从一开始连续编号。
    let mut orders: Vec<i32> = task.targets.iter().map(|t| t.order).collect();
    orders.sort();
    orders.dedup();
    let maximum = *orders.last().unwrap_or(&0);
    if orders != (1..=maximum).collect::<Vec<_>>() {
        return Err("目标时序组必须从一开始连续编号".into());
    }
    Ok(())
}

/// 模型网格遍历顺序：每列从后向前，然后遍历截面；空位也必须由模型预测。
///
/// 对应 `training/serialization.py` 的 `positions`。
pub fn positions(task: &Task) -> Vec<(i32, i32, i32)> {
    let mut grid = Vec::with_capacity((task.width * task.height * task.depth) as usize);
    for x in 0..task.width {
        for y in 0..task.height {
            for z in (-task.depth - 1)..-1 {
                grid.push((x, y, z));
            }
        }
    }
    grid
}

//! 负载摆放，对应 `training/load_placement.py`。
//!
//! 按打标器约定摆放负载：目标首块在该列最前方方块前两格（中间留一格空气）。

use crate::model::{BlockSpec, Point, Proposal};
use crate::task::Task;

/// 目标首块与结构本列最前方方块之间的固定间隔。
pub const LEAD: i32 = 2;

/// 每个截面列最前方的方块 z 坐标。
pub fn column_fronts(proposal: &Proposal) -> Vec<((i32, i32), i32)> {
    let mut fronts: Vec<((i32, i32), i32)> = Vec::new();
    for block in &proposal.blocks {
        let key = (block.position.x, block.position.y);
        match fronts.iter_mut().find(|(k, _)| *k == key) {
            Some((_, z)) => {
                if block.position.z > *z {
                    *z = block.position.z;
                }
            }
            None => fronts.push((key, block.position.z)),
        }
    }
    fronts
}

/// 把每个目标摆到该候选结构本列前端之后，需求里的 z 只作为初值保留。
pub fn align_targets(task: &Task, proposal: &Proposal) -> Task {
    let fronts = column_fronts(proposal);
    if fronts.is_empty() {
        return task.clone();
    }
    let mut aligned = task.clone();
    for target in aligned.targets.iter_mut() {
        if let Some((_, front)) = fronts
            .iter()
            .find(|(key, _)| *key == (target.x, target.y))
        {
            target.z = front + LEAD;
        }
    }
    aligned
}

/// 按目标点构造十块铁块负载的坐标；对应 `evaluator.py` 里 `loads` 的列表推导。
pub fn load_blocks(task: &Task) -> Vec<Vec<Point>> {
    task.targets
        .iter()
        .map(|target| {
            (0..crate::protocol::LOAD_BLOCKS)
                .map(|i| Point::new(target.x, target.y, target.z + i as i32))
                .collect()
        })
        .collect()
}

/// 空结构或重复方块位置；对应 `evaluator.py` 的第一道校验。
pub fn validate_proposal(proposal: &Proposal) -> Result<(), &'static str> {
    if proposal.blocks.is_empty() {
        return Err("空结构或重复方块位置");
    }
    let unique = {
        let mut positions: Vec<Point> = proposal.blocks.iter().map(|b| b.position).collect();
        positions.sort();
        positions.dedup();
        positions.len()
    };
    if unique != proposal.blocks.len() {
        return Err("空结构或重复方块位置");
    }
    Ok(())
}

/// 供外层拼装初始世界的方块规格。
pub fn iron_block_spec() -> BlockSpec {
    BlockSpec {
        kind: "iron_block".into(),
        facing: "positive_z".into(),
    }
}

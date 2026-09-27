//! 整线搬运与逐活塞激活观测，对应 `training/v2/foundation.py`。
//!
//! 当前标准下这两项只作为诊断字段保留，不覆盖主判定——通过标准是连续运行并按
//! 规定时序推完每目标十块负载。

use std::collections::{HashMap, HashSet};

use mcscai_engine::types::{BlockId, Position};
use serde::Serialize;

use crate::model::Point;
use crate::task::Task;
use crate::view::TickView;

/// 单个活塞的观测明细。
#[derive(Clone, Debug, Serialize, serde::Deserialize)]
pub struct PistonDetail {
    pub id: BlockId,
    pub initial: Point,
    pub translated: bool,
    pub piston: bool,
    pub sticky: bool,
    pub activated: bool,
    pub extended: bool,
    pub pulled: bool,
}

/// 一轮的观测结果。
#[derive(Clone, Debug, Serialize, serde::Deserialize)]
pub struct CycleDetail {
    pub cycle: i32,
    pub complete: bool,
    pub ticks: u64,
    pub translation: bool,
    pub activation: bool,
    pub translation_fraction: f64,
    pub activation_fraction: f64,
    pub extension_fraction: f64,
    pub unmoved: Vec<UnmovedBlock>,
    pub inactive_pistons: Vec<InactivePiston>,
    pub blocks: Vec<PistonDetail>,
}

#[derive(Clone, Debug, Serialize, serde::Deserialize)]
pub struct UnmovedBlock {
    pub id: BlockId,
    pub initial: Point,
    pub actual: Option<Point>,
}

#[derive(Clone, Debug, Serialize, serde::Deserialize)]
pub struct InactivePiston {
    pub id: BlockId,
    pub initial: Point,
}

/// foundation 的完整结果，对应 `result['foundation']`。
#[derive(Clone, Debug, Serialize, serde::Deserialize)]
pub struct FoundationResult {
    pub protocol: String,
    pub activation_required: bool,
    pub translation: bool,
    pub activation: bool,
    pub accepted: bool,
    pub piston_count: usize,
    pub cycles: Vec<CycleDetail>,
}

/// 一轮观测过程中的可变状态。
struct CurrentCycle {
    cycle: i32,
    ticks: u64,
    activated: HashSet<BlockId>,
    extended: HashSet<BlockId>,
    pulled: HashSet<BlockId>,
    pending_pulls: HashMap<(BlockId, u64), PendingPull>,
    snapshot: TickView,
}

struct PendingPull {
    piston_id: BlockId,
    completes_at: u64,
    members: Vec<(BlockId, Position)>,
}

/// 整线搬运与活塞激活观测器。
pub struct Foundation {
    task_rounds: i32,
    require_activation: bool,
    members: HashMap<BlockId, Position>,
    pistons: HashSet<BlockId>,
    sticky: HashSet<BlockId>,
    cycles: Vec<CycleDetail>,
    current: Option<CurrentCycle>,
    last_sequence: u64,
}

impl Foundation {
    /// 用初始快照建立观测器；`members` 为结构本体的 `(编号, 初始坐标)`。
    pub fn new(
        task: &Task,
        members: Vec<(BlockId, Position)>,
        initial: &TickView,
        require_activation: bool,
    ) -> Self {
        let pistons: HashSet<BlockId> = members
            .iter()
            .filter(|(id, _)| {
                initial
                    .block(*id)
                    .is_some_and(|b| b.kind == "piston" || b.kind == "sticky_piston")
            })
            .map(|(id, _)| *id)
            .collect();
        let sticky: HashSet<BlockId> = members
            .iter()
            .filter(|(id, _)| initial.block(*id).is_some_and(|b| b.kind == "sticky_piston"))
            .map(|(id, _)| *id)
            .collect();
        Self {
            task_rounds: task.rounds,
            require_activation,
            members: members.into_iter().collect(),
            pistons,
            sticky,
            cycles: Vec::new(),
            current: None,
            last_sequence: 0,
        }
    }

    /// 开始记录新一轮；`cycle` 传 0 起始的轮次，内部按 1 起始记录，
    /// 与 `foundation.py` 的 `dict(cycle=cycle+1, ...)` 一致。
    pub fn begin(&mut self, cycle: i32, snapshot: &TickView) {
        self.current = Some(CurrentCycle {
            cycle: cycle + 1,
            ticks: 0,
            activated: HashSet::new(),
            extended: HashSet::new(),
            pulled: HashSet::new(),
            pending_pulls: HashMap::new(),
            snapshot: snapshot.clone(),
        });
        self.observe(snapshot, 0);
    }

    /// 记录一步观测。
    pub fn observe(&mut self, snapshot: &TickView, step: u64) {
        let Some(current) = self.current.as_mut() else {
            return;
        };
        current.ticks += step;
        current.snapshot = snapshot.clone();

        for block in &snapshot.blocks {
            if self.pistons.contains(&block.id) && block.powered {
                current.activated.insert(block.id);
            }
        }
        for event in &snapshot.events {
            if event.sequence <= self.last_sequence {
                continue;
            }
            if let Some(block_id) = event.block_id {
                if self.pistons.contains(&block_id) {
                    if event.kind == "piston_powered" {
                        current.activated.insert(block_id);
                    } else if event.kind == "piston_extension_completed" {
                        current.extended.insert(block_id);
                    }
                }
            }
        }
        self.last_sequence = snapshot
            .events
            .iter()
            .map(|event| event.sequence)
            .max()
            .unwrap_or(self.last_sequence);

        // 普通活塞回缩也有 pull motion；只有确实拉动方块才算回拉。
        for motion in &snapshot.motions {
            if motion.kind == "pull"
                && self.sticky.contains(&motion.piston_id)
                && !motion.members.is_empty()
            {
                current.pending_pulls.insert(
                    (motion.piston_id, motion.started_at),
                    PendingPull {
                        piston_id: motion.piston_id,
                        completes_at: motion.completes_at,
                        members: motion.members.clone(),
                    },
                );
            }
        }
        let mut finished = Vec::new();
        for (key, motion) in current.pending_pulls.iter() {
            if snapshot.tick >= motion.completes_at
                && motion.members.iter().all(|(block_id, to)| {
                    snapshot
                        .block(*block_id)
                        .map(|b| b.position == *to)
                        .unwrap_or(false)
                })
            {
                finished.push((*key, motion.piston_id));
            }
        }
        for (key, piston_id) in finished {
            current.pending_pulls.remove(&key);
            current.pulled.insert(piston_id);
        }
    }

    /// 结束本轮记录。
    pub fn end(&mut self, complete: bool) {
        let Some(current) = self.current.take() else {
            return;
        };
        let cycle = current.cycle;
        let actual: HashMap<BlockId, Position> = current
            .snapshot
            .blocks
            .iter()
            .map(|block| (block.id, block.position))
            .collect();

        let moved: HashSet<BlockId> = self
            .members
            .iter()
            .filter(|(id, position)| {
                actual
                    .get(id)
                    .is_some_and(|p| *p == Position::new(position.x, position.y, position.z + cycle))
            })
            .map(|(id, _)| *id)
            .collect();
        let mut missing: Vec<BlockId> = self
            .members
            .keys()
            .filter(|id| !moved.contains(id))
            .copied()
            .collect();
        missing.sort();
        let mut inactive: Vec<BlockId> = self
            .pistons
            .iter()
            .filter(|id| !current.activated.contains(id))
            .copied()
            .collect();
        inactive.sort();

        let detail = CycleDetail {
            cycle,
            complete,
            ticks: current.ticks,
            translation: complete && missing.is_empty(),
            activation: complete && inactive.is_empty(),
            translation_fraction: moved.len() as f64 / self.members.len().max(1) as f64,
            activation_fraction: current.activated.len() as f64 / self.pistons.len().max(1) as f64,
            extension_fraction: current.extended.len() as f64 / self.pistons.len().max(1) as f64,
            unmoved: missing
                .iter()
                .map(|id| UnmovedBlock {
                    id: *id,
                    initial: point_of(&self.members, *id),
                    actual: actual.get(id).map(|p| Point::new(p.x, p.y, p.z)),
                })
                .collect(),
            inactive_pistons: inactive
                .iter()
                .map(|id| InactivePiston {
                    id: *id,
                    initial: point_of(&self.members, *id),
                })
                .collect(),
            blocks: self
                .members
                .iter()
                .map(|(id, position)| PistonDetail {
                    id: *id,
                    initial: Point::new(position.x, position.y, position.z),
                    translated: moved.contains(id),
                    piston: self.pistons.contains(id),
                    sticky: self.sticky.contains(id),
                    activated: current.activated.contains(id),
                    extended: current.extended.contains(id),
                    pulled: current.pulled.contains(id),
                })
                .collect(),
        };
        self.cycles.push(detail);
        self.current = None;
    }

    /// 把结果写进判定输出。
    pub fn finish(&mut self, result: &mut crate::model::Evaluation) {
        if self.current.is_some() {
            self.end(false);
        }
        let complete =
            self.cycles.len() == self.task_rounds as usize && self.cycles.iter().all(|c| c.complete);
        let translation = complete && self.cycles.iter().all(|c| c.translation);
        let activation = complete && self.cycles.iter().all(|c| c.activation);
        let accepted = translation && (activation || !self.require_activation);
        result.foundation = Some(FoundationResult {
            protocol: if self.require_activation {
                "whole_line_and_each_piston_v1".to_string()
            } else {
                "whole_line_activation_diagnostic_v2".to_string()
            },
            activation_required: self.require_activation,
            translation,
            activation,
            accepted,
            piston_count: self.pistons.len(),
            cycles: self.cycles.clone(),
        });
    }
}

fn point_of(members: &HashMap<BlockId, Position>, id: BlockId) -> Point {
    members
        .get(&id)
        .map(|p| Point::new(p.x, p.y, p.z))
        .unwrap_or_default()
}

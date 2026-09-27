//! 从引擎世界直接读取的轻量状态视图。
//!
//! `evaluator.py` 每一步都构造完整 JSON 快照再解析，是因为它跨语言。原生侧不需要
//! 付这份代价：判定热循环只读取它真正用到的字段。完整 JSON 快照只在需要回放时才构造。

use mcscai_engine::{
    simulation::Simulator,
    types::{BlockId, Position},
    world::{ArmPhase, MotionKind},
};

use crate::model::{BlockEntry, BlockSpec, Point};
use crate::protocol::STATES;

/// 方块种类与朝向的名称。
fn names(block: &mcscai_engine::types::Block) -> (&'static str, &'static str) {
    let kind = match block.kind {
        mcscai_engine::types::BlockKind::SlimeBlock => "slime_block",
        mcscai_engine::types::BlockKind::HoneyBlock => "honey_block",
        mcscai_engine::types::BlockKind::Piston => "piston",
        mcscai_engine::types::BlockKind::StickyPiston => "sticky_piston",
        mcscai_engine::types::BlockKind::Observer => "observer",
        mcscai_engine::types::BlockKind::RedstoneBlock => "redstone_block",
        mcscai_engine::types::BlockKind::IronBlock => "iron_block",
        mcscai_engine::types::BlockKind::Glass => "glass",
        mcscai_engine::types::BlockKind::LightBlueGlazedTerracotta => {
            "light_blue_glazed_terracotta"
        }
    };
    let facing = match block.facing {
        mcscai_engine::types::Direction::PositiveX => "positive_x",
        mcscai_engine::types::Direction::NegativeX => "negative_x",
        mcscai_engine::types::Direction::PositiveY => "positive_y",
        mcscai_engine::types::Direction::NegativeY => "negative_y",
        mcscai_engine::types::Direction::PositiveZ => "positive_z",
        mcscai_engine::types::Direction::NegativeZ => "negative_z",
    };
    (kind, facing)
}

/// 一个方块在当前刻度下的状态。
#[derive(Clone, Debug)]
pub struct BlockView {
    pub id: BlockId,
    pub position: Position,
    pub kind: &'static str,
    pub facing: &'static str,
    pub powered: bool,
    pub piston_phase: Option<&'static str>,
}

impl BlockView {
    /// 当前是否完全回缩（含受阻状态）。
    pub fn is_fully_retracted(&self) -> bool {
        matches!(self.piston_phase, Some("retracted") | Some("blocked"))
    }

    pub fn point(&self) -> Point {
        Point::new(self.position.x, self.position.y, self.position.z)
    }
}

/// 一个活塞臂。
#[derive(Clone, Debug)]
pub struct ArmView {
    pub piston_id: BlockId,
    pub position: Position,
}

/// 一次运动。
#[derive(Clone, Debug)]
pub struct MotionView {
    pub piston_id: BlockId,
    pub kind: &'static str,
    pub started_at: u64,
    pub completes_at: u64,
    /// 运动成员的 `(方块编号, 目标坐标)`。
    pub members: Vec<(BlockId, Position)>,
}

/// 一条新增事件中判定与观测需要的字段。
#[derive(Clone, Debug)]
pub struct EventView {
    pub sequence: u64,
    pub kind: &'static str,
    pub block_id: Option<BlockId>,
}

/// 某一刻的世界状态视图。
#[derive(Clone, Debug)]
pub struct TickView {
    pub tick: u64,
    pub blocks: Vec<BlockView>,
    pub arms: Vec<ArmView>,
    pub motions: Vec<MotionView>,
    pub events: Vec<EventView>,
}

impl TickView {
    /// 按方块编号取方块。
    pub fn block(&self, id: BlockId) -> Option<&BlockView> {
        self.blocks.iter().find(|b| b.id == id)
    }

    /// 按坐标取方块。
    pub fn block_at(&self, point: Point) -> Option<&BlockView> {
        self.blocks
            .iter()
            .find(|b| b.position.x == point.x && b.position.y == point.y && b.position.z == point.z)
    }

    /// 该坐标是否被方块或活塞臂占用；对应评估器里 `blocked` 集合的用法。
    pub fn is_blocked(&self, point: Point) -> bool {
        let occupied = self.blocks.iter().any(|b| {
            b.position.x == point.x && b.position.y == point.y && b.position.z == point.z
        });
        let armed = self.arms.iter().any(|a| {
            a.position.x == point.x && a.position.y == point.y && a.position.z == point.z
        });
        occupied || armed
    }

    /// 转成领域规则与 foundation 需要的方块表。
    pub fn entries(&self) -> Vec<BlockEntry> {
        self.blocks
            .iter()
            .map(|block| BlockEntry {
                position: block.point(),
                block: BlockSpec {
                    kind: block.kind.to_string(),
                    facing: block.facing.to_string(),
                },
            })
            .collect()
    }

    /// 推出运动列表，字段为 `(活塞编号, 运动类型, 活塞坐标)`。
    pub fn push_motions(&self) -> Vec<(i64, String, Point)> {
        self.motions
            .iter()
            .map(|motion| {
                let position = self
                    .block(motion.piston_id)
                    .map(|b| b.point())
                    .unwrap_or_default();
                (motion.piston_id as i64, motion.kind.to_string(), position)
            })
            .collect()
    }
}

/// 从引擎读取当前刻的状态视图；`since_sequence` 之前的旧事件被过滤掉。
pub fn view(engine: &Simulator, since_sequence: u64) -> TickView {
    let tick = engine.tick();
    let world = engine.world();

    let blocks = world
        .blocks()
        .iter()
        .map(|(position, block)| {
            let (kind, facing) = names(block);
            BlockView {
                id: block.id,
                position: *position,
                kind,
                facing,
                powered: block.powered,
                piston_phase: block.piston_phase.map(|phase| match phase {
                    mcscai_engine::types::PistonPhase::Retracted => "retracted",
                    mcscai_engine::types::PistonPhase::ExtensionPending { .. } => "extension_pending",
                    mcscai_engine::types::PistonPhase::Extending { .. } => "extending",
                    mcscai_engine::types::PistonPhase::Extended => "extended",
                    mcscai_engine::types::PistonPhase::RetractionPending { .. } => {
                        "retraction_pending"
                    }
                    mcscai_engine::types::PistonPhase::Retracting { .. } => "retracting",
                    mcscai_engine::types::PistonPhase::Blocked => "blocked",
                }),
            }
        })
        .collect();

    let arms = world
        .arms()
        .values()
        .map(|arm| ArmView {
            piston_id: arm.piston_id,
            position: arm.position,
        })
        .collect();

    let motions = world
        .motions()
        .values()
        .map(|motion| MotionView {
            piston_id: motion.piston_id,
            kind: match motion.kind {
                MotionKind::Push => "push",
                MotionKind::Pull => "pull",
            },
            started_at: motion.started_at,
            completes_at: motion.completes_at,
            members: motion
                .blocks
                .iter()
                .map(|block| (block.block_id, block.to))
                .collect(),
        })
        .collect();

    let events = engine
        .events()
        .iter()
        .filter(|event| event.sequence > since_sequence)
        .map(|event| EventView {
            sequence: event.sequence,
            kind: event_kind(event.kind),
            block_id: event.block_id,
        })
        .collect();

    TickView {
        tick,
        blocks,
        arms,
        motions,
        events,
    }
}

/// 事件类型的名称，与 `python_snapshot.rs` 保持一致。
pub fn event_kind(kind: mcscai_engine::simulation::SimulationEventKind) -> &'static str {
    use mcscai_engine::simulation::SimulationEventKind::*;
    match kind {
        BlockPlaced => "block_placed",
        BlockRemoved => "block_removed",
        WorldCleared => "world_cleared",
        WorldReplaced => "world_replaced",
        CheckpointCreated => "checkpoint_created",
        CheckpointRestored => "checkpoint_restored",
        PistonPowered => "piston_powered",
        PistonUnpowered => "piston_unpowered",
        PistonExtensionScheduled => "piston_extension_scheduled",
        PistonExtensionStarted => "piston_extension_started",
        PistonExtensionCompleted => "piston_extension_completed",
        PistonExtensionBlocked => "piston_extension_blocked",
        PistonRetractionScheduled => "piston_retraction_scheduled",
        PistonRetractionStarted => "piston_retraction_started",
        PistonRetractionCompleted => "piston_retraction_completed",
        PistonPullSkipped => "piston_pull_skipped",
        BlockMoved => "block_moved",
        ObserverPulseScheduled => "observer_pulse_scheduled",
        ObserverPulseStarted => "observer_pulse_started",
        ObserverPulseEnded => "observer_pulse_ended",
    }
}

/// 判断某个 token 是否属于「活塞」类方块。
pub fn is_piston_token(token: usize) -> bool {
    matches!(STATES.get(token), Some(("piston", _)) | Some(("sticky_piston", _)))
}

/// 活塞臂阶段的名称。
pub fn arm_phase(phase: ArmPhase) -> &'static str {
    match phase {
        ArmPhase::Extending => "extending",
        ArmPhase::Extended => "extended",
        ArmPhase::Retracting => "retracting",
    }
}

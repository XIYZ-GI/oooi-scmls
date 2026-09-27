use serde::{Deserialize, Serialize};

use crate::types::{BlockId, Position};

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SimulationEventKind {
    BlockPlaced,
    BlockRemoved,
    WorldCleared,
    WorldReplaced,
    CheckpointCreated,
    CheckpointRestored,
    PistonPowered,
    PistonUnpowered,
    PistonExtensionScheduled,
    PistonExtensionStarted,
    PistonExtensionCompleted,
    PistonExtensionBlocked,
    PistonRetractionScheduled,
    PistonRetractionStarted,
    PistonRetractionCompleted,
    PistonPullSkipped,
    BlockMoved,
    ObserverPulseScheduled,
    ObserverPulseStarted,
    ObserverPulseEnded,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct SimulationEvent {
    pub sequence: u64,
    pub tick: u64,
    pub kind: SimulationEventKind,
    pub block_id: Option<BlockId>,
    pub position: Option<Position>,
    pub from: Option<Position>,
    pub to: Option<Position>,
    pub message: String,
}

impl SimulationEvent {
    pub fn at(
        tick: u64,
        kind: SimulationEventKind,
        block_id: Option<BlockId>,
        position: Option<Position>,
        message: impl Into<String>,
    ) -> Self {
        Self {
            sequence: 0,
            tick,
            kind,
            block_id,
            position,
            from: None,
            to: None,
            message: message.into(),
        }
    }

    pub fn movement(tick: u64, block_id: BlockId, from: Position, to: Position) -> Self {
        Self {
            sequence: 0,
            tick,
            kind: SimulationEventKind::BlockMoved,
            block_id: Some(block_id),
            position: Some(to),
            from: Some(from),
            to: Some(to),
            message: format!("方块 {block_id} 从 {from:?} 移动到 {to:?}"),
        }
    }
}

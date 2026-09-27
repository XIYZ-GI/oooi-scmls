use serde::{Deserialize, Serialize};

use crate::types::{BlockId, Direction, Position};

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MotionKind {
    Push,
    Pull,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct MovingBlock {
    pub block_id: BlockId,
    pub from: Position,
    pub to: Position,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct Motion {
    pub piston_id: BlockId,
    pub kind: MotionKind,
    pub direction: Direction,
    pub started_at: u64,
    pub completes_at: u64,
    pub blocks: Vec<MovingBlock>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ArmPhase {
    Extending,
    Extended,
    Retracting,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct PistonArm {
    pub piston_id: BlockId,
    pub position: Position,
    pub facing: Direction,
    pub sticky: bool,
    pub phase: ArmPhase,
    pub started_at: u64,
    pub completes_at: Option<u64>,
}

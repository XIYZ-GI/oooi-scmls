use serde::{Deserialize, Serialize};

use crate::types::{BlockSpec, Position};

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum EngineCommand {
    SetBlock {
        position: Position,
        block: BlockSpec,
    },
    RemoveBlock {
        position: Position,
    },
    ReplaceWorld {
        blocks: Vec<WorldBlockInput>,
    },
    ClearWorld,
    CreateCheckpoint,
    RestoreCheckpoint,
    Step {
        ticks: u32,
    },
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct WorldBlockInput {
    pub position: Position,
    pub block: BlockSpec,
}

use serde::{Deserialize, Serialize};

use super::Direction;

pub type BlockId = u64;

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BlockKind {
    SlimeBlock,
    HoneyBlock,
    Piston,
    StickyPiston,
    RedstoneBlock,
    Observer,
    IronBlock,
    LightBlueGlazedTerracotta,
    Glass,
}

impl BlockKind {
    pub const fn is_adhesive(self) -> bool {
        matches!(self, Self::SlimeBlock | Self::HoneyBlock)
    }

    pub const fn can_be_strongly_powered(self) -> bool {
        matches!(
            self,
            Self::SlimeBlock | Self::HoneyBlock | Self::IronBlock | Self::LightBlueGlazedTerracotta
        )
    }

    pub const fn is_piston(self) -> bool {
        matches!(self, Self::Piston | Self::StickyPiston)
    }

    pub const fn is_sticky_piston(self) -> bool {
        matches!(self, Self::StickyPiston)
    }

    pub const fn can_be_pulled(self) -> bool {
        !matches!(self, Self::LightBlueGlazedTerracotta)
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "phase", rename_all = "snake_case")]
pub enum PistonPhase {
    #[default]
    Retracted,
    ExtensionPending {
        starts_at: u64,
    },
    Extending {
        completes_at: u64,
    },
    Extended,
    RetractionPending {
        starts_at: u64,
    },
    Retracting {
        completes_at: u64,
    },
    Blocked,
}

impl PistonPhase {
    pub const fn is_fully_retracted(self) -> bool {
        matches!(self, Self::Retracted | Self::Blocked)
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "phase", rename_all = "snake_case")]
pub enum ObserverPhase {
    #[default]
    Idle,
    PulsePending {
        starts_at: u64,
    },
    Pulsing {
        ends_at: u64,
    },
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct Block {
    pub id: BlockId,
    pub kind: BlockKind,
    pub facing: Direction,
    pub powered: bool,
    pub strongly_powered: bool,
    pub piston_phase: Option<PistonPhase>,
    pub observer_phase: Option<ObserverPhase>,
}

impl Block {
    pub fn new(id: BlockId, kind: BlockKind, facing: Direction) -> Self {
        Self {
            id,
            kind,
            facing,
            powered: false,
            strongly_powered: false,
            piston_phase: kind.is_piston().then_some(PistonPhase::Retracted),
            observer_phase: (kind == BlockKind::Observer).then_some(ObserverPhase::Idle),
        }
    }

    pub fn can_be_moved(&self) -> bool {
        if !self.kind.is_piston() {
            return true;
        }

        !self.powered
            && self
                .piston_phase
                .is_some_and(PistonPhase::is_fully_retracted)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct BlockSpec {
    pub kind: BlockKind,
    #[serde(default)]
    pub facing: Direction,
}

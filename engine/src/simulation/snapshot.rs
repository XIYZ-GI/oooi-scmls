use serde::{Deserialize, Serialize};

use crate::{
    types::{Block, Position},
    world::{Motion, PistonArm, World},
};

use super::SimulationEvent;

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct PlacedBlock {
    pub position: Position,
    #[serde(flatten)]
    pub block: Block,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct SimulationSnapshot {
    pub tick: u64,
    pub blocks: Vec<PlacedBlock>,
    pub arms: Vec<PistonArm>,
    pub motions: Vec<Motion>,
    pub events: Vec<SimulationEvent>,
}

impl SimulationSnapshot {
    pub fn from_world(tick: u64, world: &World, events: &[SimulationEvent]) -> Self {
        Self {
            tick,
            blocks: world
                .blocks()
                .iter()
                .map(|(position, block)| PlacedBlock {
                    position: *position,
                    block: block.clone(),
                })
                .collect(),
            arms: world.arms().values().cloned().collect(),
            motions: world.motions().values().cloned().collect(),
            events: events.to_vec(),
        }
    }
}

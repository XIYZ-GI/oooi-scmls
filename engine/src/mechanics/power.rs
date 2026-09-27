use std::collections::BTreeSet;

use crate::{
    types::{BlockId, BlockKind, Direction, ObserverPhase, Position},
    world::World,
};

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct PowerState {
    pub strongly_powered: BTreeSet<Position>,
    pub powered_pistons: BTreeSet<BlockId>,
}

pub fn resolve_power(world: &World) -> PowerState {
    let mut state = PowerState::default();
    let mut direct_observer_outputs = BTreeSet::new();

    for (position, block) in world.blocks() {
        if block.kind == BlockKind::Observer
            && matches!(block.observer_phase, Some(ObserverPhase::Pulsing { .. }))
        {
            let output_position = position.offset(block.facing);
            direct_observer_outputs.insert((output_position, *position));
            if world
                .block_at(output_position)
                .is_some_and(|target| target.kind.can_be_strongly_powered())
            {
                state.strongly_powered.insert(output_position);
            }
        }
    }

    for (position, block) in world.blocks() {
        if !block.kind.is_piston() {
            continue;
        }
        let input_directions = || {
            Direction::ALL
                .into_iter()
                .filter(|direction| *direction != block.facing)
        };
        let direct_redstone = input_directions().any(|direction| {
            world
                .block_at(position.offset(direction))
                .is_some_and(|neighbor| neighbor.kind == BlockKind::RedstoneBlock)
        });
        let front_position = position.offset(block.facing);
        let direct_observer = direct_observer_outputs
            .iter()
            .any(|(target, source)| target == position && *source != front_position);
        let relayed_strong_power = input_directions()
            .any(|direction| state.strongly_powered.contains(&position.offset(direction)));
        if direct_redstone || direct_observer || relayed_strong_power {
            state.powered_pistons.insert(block.id);
        }
    }

    state
}

use std::collections::{BTreeMap, BTreeSet};

use crate::types::{Block, BlockId, BlockSpec, Position};

use super::{Motion, PistonArm, WorldError};

#[derive(Clone, Debug, Default)]
pub struct World {
    blocks: BTreeMap<Position, Block>,
    locations: BTreeMap<BlockId, Position>,
    arms: BTreeMap<BlockId, PistonArm>,
    motions: BTreeMap<BlockId, Motion>,
    next_block_id: BlockId,
}

impl World {
    pub fn new() -> Self {
        Self {
            next_block_id: 1,
            ..Self::default()
        }
    }

    pub fn blocks(&self) -> &BTreeMap<Position, Block> {
        &self.blocks
    }

    pub fn arms(&self) -> &BTreeMap<BlockId, PistonArm> {
        &self.arms
    }

    pub fn motions(&self) -> &BTreeMap<BlockId, Motion> {
        &self.motions
    }

    pub fn block_at(&self, position: Position) -> Option<&Block> {
        self.blocks.get(&position)
    }

    pub fn block_at_mut(&mut self, position: Position) -> Option<&mut Block> {
        self.blocks.get_mut(&position)
    }

    pub fn block_position(&self, id: BlockId) -> Option<Position> {
        self.locations.get(&id).copied()
    }

    pub fn block_by_id(&self, id: BlockId) -> Option<&Block> {
        self.block_position(id)
            .and_then(|position| self.block_at(position))
    }

    pub fn block_by_id_mut(&mut self, id: BlockId) -> Option<&mut Block> {
        let position = self.block_position(id)?;
        self.block_at_mut(position)
    }

    pub fn block_ids(&self) -> Vec<BlockId> {
        self.locations.keys().copied().collect()
    }

    pub fn insert(&mut self, position: Position, spec: BlockSpec) -> Result<BlockId, WorldError> {
        self.ensure_editable(position)?;
        if self.blocks.contains_key(&position) {
            return Err(WorldError::Occupied(position));
        }

        let id = self.next_block_id;
        self.next_block_id += 1;
        let block = Block::new(id, spec.kind, spec.facing);
        self.blocks.insert(position, block);
        self.locations.insert(id, position);
        Ok(id)
    }

    pub fn set(&mut self, position: Position, spec: BlockSpec) -> Result<BlockId, WorldError> {
        self.ensure_editable(position)?;
        if let Some(previous) = self.blocks.remove(&position) {
            self.locations.remove(&previous.id);
        }
        self.insert(position, spec)
    }

    pub fn remove(&mut self, position: Position) -> Result<Block, WorldError> {
        self.ensure_editable(position)?;
        let block = self
            .blocks
            .remove(&position)
            .ok_or(WorldError::Missing(position))?;
        self.locations.remove(&block.id);
        Ok(block)
    }

    pub fn clear(&mut self) {
        *self = Self::new();
    }

    pub fn arm_at(&self, position: Position) -> Option<&PistonArm> {
        self.arms.values().find(|arm| arm.position == position)
    }

    pub fn moving_block_ids(&self) -> BTreeSet<BlockId> {
        self.motions
            .values()
            .flat_map(|motion| motion.blocks.iter().map(|block| block.block_id))
            .collect()
    }

    pub fn reserved_positions(&self) -> BTreeSet<Position> {
        self.motions
            .values()
            .flat_map(|motion| motion.blocks.iter().map(|block| block.to))
            .collect()
    }

    pub fn add_motion(&mut self, motion: Motion, arm: PistonArm) {
        self.arms.insert(motion.piston_id, arm);
        self.motions.insert(motion.piston_id, motion);
    }

    pub fn motion_for(&self, piston_id: BlockId) -> Option<&Motion> {
        self.motions.get(&piston_id)
    }

    pub fn complete_motion(&mut self, piston_id: BlockId) -> Result<Motion, WorldError> {
        let motion = self
            .motions
            .remove(&piston_id)
            .ok_or(WorldError::MissingBlock(piston_id))?;

        let mut moved = Vec::with_capacity(motion.blocks.len());
        for item in &motion.blocks {
            let block = self
                .blocks
                .remove(&item.from)
                .ok_or(WorldError::MissingBlock(item.block_id))?;
            moved.push((item.to, block));
        }
        for (position, block) in moved {
            self.locations.insert(block.id, position);
            self.blocks.insert(position, block);
        }
        Ok(motion)
    }

    pub fn set_arm(&mut self, piston_id: BlockId, arm: PistonArm) {
        self.arms.insert(piston_id, arm);
    }

    pub fn remove_arm(&mut self, piston_id: BlockId) {
        self.arms.remove(&piston_id);
    }

    fn ensure_editable(&self, position: Position) -> Result<(), WorldError> {
        let moving = self.moving_block_ids();
        let occupied_by_moving_block = self
            .block_at(position)
            .is_some_and(|block| moving.contains(&block.id));
        if occupied_by_moving_block
            || self.reserved_positions().contains(&position)
            || self.arm_at(position).is_some()
        {
            return Err(WorldError::Busy(position));
        }
        Ok(())
    }
}

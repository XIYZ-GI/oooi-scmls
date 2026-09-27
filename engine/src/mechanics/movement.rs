use std::collections::{BTreeSet, VecDeque};

use thiserror::Error;

use crate::{
    types::{BlockId, Direction, Position},
    world::{MovingBlock, World},
};

use super::blocks_stick;

pub const PISTON_PUSH_LIMIT: usize = 12;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MovementMode {
    Push,
    Pull,
}

#[derive(Clone, Debug, Error, Eq, PartialEq)]
pub enum MovementError {
    #[error("方块 {block_id} 处于运动中")]
    BlockInMotion { block_id: BlockId },
    #[error("坐标 {position:?} 被活塞臂占用")]
    PistonArmCollision { position: Position },
    #[error("方块 {block_id} 当前不可推动")]
    ImmovableBlock { block_id: BlockId },
    #[error("推动方块数量 {count} 超过 12 个上限")]
    PushLimitExceeded { count: usize },
    #[error("坐标 {position:?} 已被其他运动过程预留")]
    ReservedPosition { position: Position },
}

pub fn plan_movement(
    world: &World,
    root: Position,
    direction: Direction,
    mode: MovementMode,
    piston_id: BlockId,
) -> Result<Vec<MovingBlock>, MovementError> {
    if world
        .arm_at(root)
        .is_some_and(|arm| arm.piston_id != piston_id)
    {
        return Err(MovementError::PistonArmCollision { position: root });
    }
    let Some(root_block) = world.block_at(root) else {
        return Ok(Vec::new());
    };
    if mode == MovementMode::Pull && !root_block.kind.can_be_pulled() {
        return Ok(Vec::new());
    }

    let moving_ids = world.moving_block_ids();
    let reserved_positions = world.reserved_positions();
    let mut included = BTreeSet::new();
    let mut queue = VecDeque::from([root]);

    while let Some(position) = queue.pop_front() {
        if included.contains(&position) {
            continue;
        }
        if world
            .arm_at(position)
            .is_some_and(|arm| arm.piston_id != piston_id)
        {
            return Err(MovementError::PistonArmCollision { position });
        }
        let Some(block) = world.block_at(position) else {
            continue;
        };
        if moving_ids.contains(&block.id) {
            return Err(MovementError::BlockInMotion { block_id: block.id });
        }
        if !block.can_be_moved() {
            return Err(MovementError::ImmovableBlock { block_id: block.id });
        }

        included.insert(position);
        if included.len() > PISTON_PUSH_LIMIT {
            return Err(MovementError::PushLimitExceeded {
                count: included.len(),
            });
        }

        let destination = position.offset(direction);
        if reserved_positions.contains(&destination) {
            return Err(MovementError::ReservedPosition {
                position: destination,
            });
        }
        if world
            .arm_at(destination)
            .is_some_and(|arm| arm.piston_id != piston_id)
        {
            return Err(MovementError::PistonArmCollision {
                position: destination,
            });
        }
        if world.block_at(destination).is_some() && !included.contains(&destination) {
            queue.push_back(destination);
        }

        if block.kind.is_adhesive() {
            for neighbor_direction in Direction::ALL {
                let neighbor = position.offset(neighbor_direction);
                if let Some(neighbor_block) = world.block_at(neighbor) {
                    if neighbor_block.id != piston_id
                        // 已进入另一运动的方块是移动占位，不再参加新的侧向黏附。
                        // 正面推进仍经过上面的目标位置检查，不能穿过运动方块。
                        && !moving_ids.contains(&neighbor_block.id)
                        && blocks_stick(block.kind, neighbor_block.kind)
                    {
                        queue.push_back(neighbor);
                    }
                }
            }
        }
    }

    Ok(included
        .into_iter()
        .map(|from| MovingBlock {
            block_id: world.block_at(from).expect("移动集合必须存在").id,
            from,
            to: from.offset(direction),
        })
        .collect())
}

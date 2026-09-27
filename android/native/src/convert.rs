//! 字符串方块规格与引擎强类型之间的转换。

use mcscai_engine::{
    simulation::WorldBlockInput,
    types::{BlockKind, BlockSpec as EngineBlockSpec, Direction, Position},
};

use crate::model::{BlockEntry, BlockSpec, Point};

/// 把引擎坐标转成模型坐标。
pub fn point(position: Position) -> Point {
    Point::new(position.x, position.y, position.z)
}

/// 把模型坐标转成引擎坐标。
pub fn position(point: Point) -> Position {
    Position::new(point.x, point.y, point.z)
}

/// 解析方块种类名；`air` 与未知种类都返回 `None`。
pub fn parse_kind(kind: &str) -> Option<BlockKind> {
    Some(match kind {
        "slime_block" => BlockKind::SlimeBlock,
        "honey_block" => BlockKind::HoneyBlock,
        "piston" => BlockKind::Piston,
        "sticky_piston" => BlockKind::StickyPiston,
        "observer" => BlockKind::Observer,
        "redstone_block" => BlockKind::RedstoneBlock,
        "iron_block" => BlockKind::IronBlock,
        "glass" => BlockKind::Glass,
        "light_blue_glazed_terracotta" => BlockKind::LightBlueGlazedTerracotta,
        _ => return None,
    })
}

/// 解析朝向名；未知朝向返回 `None`。
pub fn parse_direction(facing: &str) -> Option<Direction> {
    Some(match facing {
        "positive_x" => Direction::PositiveX,
        "negative_x" => Direction::NegativeX,
        "positive_y" => Direction::PositiveY,
        "negative_y" => Direction::NegativeY,
        "positive_z" => Direction::PositiveZ,
        "negative_z" => Direction::NegativeZ,
        _ => return None,
    })
}

/// 转成引擎的方块规格。
pub fn engine_spec(spec: &BlockSpec) -> Option<EngineBlockSpec> {
    Some(EngineBlockSpec {
        kind: parse_kind(&spec.kind)?,
        facing: parse_direction(&spec.facing).unwrap_or_default(),
    })
}

/// 转成引擎的世界方块输入。
pub fn world_block(entry: &BlockEntry) -> Option<WorldBlockInput> {
    Some(WorldBlockInput {
        position: position(entry.position),
        block: engine_spec(&entry.block)?,
    })
}

/// 构造一个引擎世界方块输入。
pub fn world_block_at(point: Point, kind: &str) -> Option<WorldBlockInput> {
    Some(WorldBlockInput {
        position: position(point),
        block: EngineBlockSpec {
            kind: parse_kind(kind)?,
            facing: Direction::PositiveZ,
        },
    })
}

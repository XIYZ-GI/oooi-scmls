//! 生成预筛的类型化Python入口，仅传入布局和输出要求，返回判定。

use pyo3::{exceptions::PyValueError, prelude::*};

use crate::{
    simulation::{preflight, WorldBlockInput},
    types::{BlockKind, BlockSpec, Direction, Position},
};

type InputBlock = (i32, i32, i32, String, String);

#[pyfunction]
pub fn generator_preflight(
    py: Python<'_>,
    blocks: Vec<InputBlock>,
    outputs: Vec<(i32, i32, i32, u64)>,
    period: u32,
) -> PyResult<(bool, String)> {
    let blocks = blocks
        .into_iter()
        .map(|(x, y, z, kind, facing)| {
            if [x, y, z].iter().any(|v| v.unsigned_abs() > 1_000_000) {
                return Err(PyValueError::new_err("预筛坐标超出预算"));
            }
            let kind = match kind.as_str() {
                "slime_block" => BlockKind::SlimeBlock,
                "honey_block" => BlockKind::HoneyBlock,
                "piston" => BlockKind::Piston,
                "sticky_piston" => BlockKind::StickyPiston,
                "observer" => BlockKind::Observer,
                "iron_block" => BlockKind::IronBlock,
                "redstone_block" => BlockKind::RedstoneBlock,
                "glass" => BlockKind::Glass,
                "light_blue_glazed_terracotta" => BlockKind::LightBlueGlazedTerracotta,
                _ => return Err(PyValueError::new_err("非法方块类型")),
            };
            let facing = match facing.as_str() {
                "positive_x" => Direction::PositiveX,
                "negative_x" => Direction::NegativeX,
                "positive_y" => Direction::PositiveY,
                "negative_y" => Direction::NegativeY,
                "positive_z" => Direction::PositiveZ,
                "negative_z" => Direction::NegativeZ,
                _ => return Err(PyValueError::new_err("非法方块朝向")),
            };
            Ok(WorldBlockInput {
                position: Position::new(x, y, z),
                block: BlockSpec { kind, facing },
            })
        })
        .collect::<PyResult<Vec<_>>>()?;
    let outputs = outputs
        .into_iter()
        .map(|(x, y, z, t)| {
            if [x, y, z].iter().any(|v| v.unsigned_abs() > 1_000_000) || t > 1004 {
                return Err(PyValueError::new_err("预筛输出超出预算"));
            }
            Ok((Position::new(x, y, z), t))
        })
        .collect::<PyResult<Vec<_>>>()?;
    let reason = py
        .allow_threads(move || preflight(blocks, outputs, period))
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((reason.is_none(), reason.unwrap_or("").to_owned()))
}

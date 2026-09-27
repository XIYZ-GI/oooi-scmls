//! 连续两轮生成预筛，直接读取世界状态，不构造或序列化快照。

use std::collections::BTreeSet;

use crate::types::{BlockKind, BlockSpec, Direction, PistonPhase, Position};

use super::{SimulationError, SimulationEventKind, Simulator, WorldBlockInput};

pub fn preflight(
    body: Vec<WorldBlockInput>,
    outputs: Vec<(Position, u64)>,
    period: u32,
) -> Result<Option<&'static str>, SimulationError> {
    if !(4..=1004).contains(&period) || body.len() > 4096 || outputs.len() > 32 {
        return Err(SimulationError::InvalidCommand("预筛输入超出预算".into()));
    }
    let mut members: Vec<Position> = body.iter().map(|v| v.position).collect();
    let mut world = body;
    for (p, _) in &outputs {
        for i in 0..10 {
            let position = p.translated(Direction::PositiveZ, 2 + i);
            members.push(position);
            world.push(WorldBlockInput {
                position,
                block: spec(BlockKind::IronBlock),
            });
        }
    }
    let mut actuator = Position::new(0, 0, -1);
    let mut power = Position::new(0, 0, -2);
    world.push(WorldBlockInput {
        position: actuator,
        block: spec(BlockKind::Piston),
    });
    world.push(WorldBlockInput {
        position: power,
        block: spec(BlockKind::RedstoneBlock),
    });
    if world
        .iter()
        .map(|v| v.position)
        .collect::<BTreeSet<_>>()
        .len()
        != world.len()
    {
        return Ok(Some("预筛：外部装置或负载重叠"));
    }
    let mut engine = Simulator::new();
    engine.replace_world(world)?;
    let members: Vec<_> = members
        .into_iter()
        .map(|p| (engine.world().block_at(p).unwrap().id, p))
        .collect();
    let outputs: Vec<_> = outputs
        .into_iter()
        .map(|(p, tick)| {
            engine
                .world()
                .block_at(p)
                .map(|b| (b.id, tick))
                .ok_or_else(|| SimulationError::InvalidCommand("输出位置没有方块".into()))
        })
        .collect::<Result<_, _>>()?;
    for cycle in 0..2 {
        engine.step_many(4)?;
        engine.remove_block(power)?;
        engine.step_many(period - 4)?;
        for (id, p) in &members {
            if engine.world().block_position(*id)
                != Some(p.translated(Direction::PositiveZ, cycle + 1))
            {
                return Ok(Some("预筛：本体或负载未连续平移一格"));
            }
        }
        // 与原接口一致，只使用引擎保留的事件窗口，不改变事件淘汰语义。
        let offset = cycle as u64 * period as u64;
        for (id, expected) in &outputs {
            let actual = engine
                .events
                .iter()
                .filter(|e| {
                    e.block_id == Some(*id)
                        && e.kind == SimulationEventKind::PistonExtensionCompleted
                        && e.tick > offset
                })
                .map(|e| e.tick)
                .min();
            if actual != Some(expected + offset) {
                return Ok(Some("预筛：输出激活时刻不符"));
            }
        }
        if cycle == 0 {
            if !engine
                .world()
                .block_at(actuator)
                .is_some_and(|b| b.piston_phase == Some(PistonPhase::Retracted))
            {
                return Ok(Some("预筛：外部推动器未回缩"));
            }
            let next_actuator = Position::new(0, 0, 0);
            let next_power = Position::new(0, 0, -1);
            let blocked = [next_actuator, next_power].iter().any(|p| {
                (*p != actuator && engine.world().block_at(*p).is_some())
                    || engine.world().arm_at(*p).is_some()
            });
            engine.remove_block(actuator)?;
            if blocked {
                return Ok(Some("预筛：下一轮推动装置受阻"));
            }
            actuator = next_actuator;
            power = next_power;
            engine.set_block(actuator, spec(BlockKind::Piston))?;
            engine.set_block(power, spec(BlockKind::RedstoneBlock))?;
        }
    }
    Ok(None)
}

fn spec(kind: BlockKind) -> BlockSpec {
    BlockSpec {
        kind,
        facing: Direction::PositiveZ,
    }
}

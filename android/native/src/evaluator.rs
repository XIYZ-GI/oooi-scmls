//! 完整候选的固定周期模拟，对应 `training/evaluator.py`。
//!
//! 判定标准：连续运行、按需求时序推完每目标十块负载。整线是否平移与逐活塞是否
//! 激活只作为诊断，不覆盖主判定。时序或时限不合格但每目标负载确实都在前进时记为
//! **半通过**，便于上层优先展示。
//!
//! 本文件与 Python 版逐字段对齐；`tests/` 下的一致性用例负责兜住两端不跑偏。

use std::collections::{HashMap, HashSet};
use std::time::Instant;

use mcscai_engine::{
    simulation::{EngineCommand, Simulator, WorldBlockInput},
    types::{BlockId, Position},
};

use crate::convert;
use crate::domain_rules;
use crate::foundation::Foundation;
use crate::model::{
    BodyDiagnostic, EvaluateRequest, Evaluation, Point, RoundOutcome, TraceFrame,
};
use crate::protocol::{LOAD_BLOCKS, ROUND_GAP_TICKS, SAFETY_TICKS, STALL_TICKS, TIME_LIMIT_SECONDS};
use crate::view::{self, TickView};

/// 判定过程中的可变状态。
struct Judge<'a> {
    request: &'a EvaluateRequest,
    engine: Simulator,
    result: Evaluation,
    started: Instant,
    trace: Vec<TraceFrame>,
    last_sequence: u64,
    base_version: String,
}

impl<'a> Judge<'a> {
    /// 执行一条命令，按需记录回放，并返回当前刻的状态视图。
    fn apply(&mut self, command: EngineCommand) -> Result<TickView, String> {
        self.engine
            .execute(command.clone())
            .map_err(|error| format!("模拟输入不合法：{error}"))?;
        if let EngineCommand::Step { ticks } = command {
            self.result.simulated_ticks += ticks as u64;
        }
        if self.request.options.capture {
            let frame = TraceFrame {
                command: command_to_json(&command),
                snapshot: serde_json::to_value(self.engine.snapshot())
                    .map_err(|error| format!("状态序列化失败：{error}"))?,
            };
            self.last_sequence = frame
                .snapshot
                .get("events")
                .and_then(|events| events.as_array())
                .map(|events| {
                    events
                        .iter()
                        .filter_map(|event| event.get("sequence").and_then(|s| s.as_u64()))
                        .max()
                        .unwrap_or(self.last_sequence)
                })
                .unwrap_or(self.last_sequence);
            self.trace.push(frame);
        }
        Ok(view::view(&self.engine, 0))
    }

    /// 判定失败，汇总已观测到的信息。
    fn fail(&mut self, reason: impl AsRef<str>) -> Evaluation {
        let reason = reason.as_ref();
        self.result.reason = reason.to_string();
        self.result.seconds = Some(self.started.elapsed().as_secs_f64());
        if self.request.options.capture {
            self.result.trace = Some(std::mem::take(&mut self.trace));
        }
        self.result.clone()
    }
}

impl<'a> Judge<'a> {
    /// 判定成功后汇总。
    fn succeed(&mut self) -> Evaluation {
        self.result.accepted = true;
        self.result.seconds = Some(self.started.elapsed().as_secs_f64());
        if self.request.options.capture {
            self.result.trace = Some(std::mem::take(&mut self.trace));
        }
        self.result.clone()
    }
}

/// 把引擎命令转成回放用的 JSON，字段与 `command_to_json` 的 wire 格式一致。
fn command_to_json(command: &EngineCommand) -> serde_json::Value {
    serde_json::to_value(command).unwrap_or(serde_json::Value::Null)
}

/// 判定一个候选。
pub fn evaluate(request: &EvaluateRequest) -> Evaluation {
    let mut judge = Judge {
        request,
        engine: Simulator::new(),
        result: Evaluation::new(&mcscai_engine_version()),
        started: Instant::now(),
        trace: Vec::new(),
        last_sequence: 0,
        base_version: String::new(),
    };
    judge.result.engine_version = mcscai_engine_version();
    let _ = &judge.base_version;
    run(&mut judge)
}

/// 读取引擎版本号。
///
/// 取自 `engine/Cargo.toml`，与 Python 侧 `mcscai_engine.__version__` 同源，
/// 由 `build.rs` 在编译期注入。
fn mcscai_engine_version() -> String {
    env!("MCSCAI_ENGINE_VERSION").to_string()
}

fn run(judge: &mut Judge<'_>) -> Evaluation {
    let task = judge.request.task.clone();
    let proposal = judge.request.proposal.clone();
    let options = judge.request.options;

    // 结构本身的静态校验。
    let mut occupied: HashSet<Point> = HashSet::new();
    for entry in &proposal.blocks {
        occupied.insert(entry.position);
    }
    if proposal.blocks.is_empty() || occupied.len() != proposal.blocks.len() {
        return judge.fail("空结构或重复方块位置");
    }
    if proposal.blocks.iter().any(|entry| {
        let p = entry.position;
        !(0 <= p.x
            && p.x < task.width
            && 0 <= p.y
            && p.y < task.height
            && -task.depth - 1 <= p.z
            && p.z <= -2)
    }) {
        return judge.fail("结构超出初始设计空间");
    }
    if proposal.blocks.iter().any(|entry| {
        crate::protocol::state_id(&entry.block.kind, &entry.block.facing).is_none()
    }) {
        return judge.fail("非法方块或方向");
    }
    if !occupied.contains(&proposal.push)
        || occupied.iter().any(|p| {
            p.x == proposal.push.x && p.y == proposal.push.y && p.z < proposal.push.z
        })
    {
        return judge.fail("推动点不是所在列后方可接触的方块");
    }
    let issues = domain_rules::proposal_issues(&proposal);
    if !issues.is_empty() {
        judge.result.design_issues =
            Some(issues.iter().map(|issue| issue.to_json()).collect());
        return judge.fail(domain_rules::reason());
    }

    // 十块负载、外部推动器与供电位置。
    let mut actuator = Point::new(proposal.push.x, proposal.push.y, proposal.push.z - 1);
    let mut power = Point::new(proposal.push.x, proposal.push.y, proposal.push.z - 2);

    let mut world: Vec<WorldBlockInput> = Vec::new();
    for entry in &proposal.blocks {
        match convert::world_block(entry) {
            Some(item) => world.push(item),
            None => return judge.fail("非法方块或方向"),
        }
    }
    for target in &task.targets {
        for i in 0..LOAD_BLOCKS {
            match convert::world_block_at(
                Point::new(target.x, target.y, target.z + i as i32),
                "iron_block",
            ) {
                Some(item) => world.push(item),
                None => return judge.fail("非法方块或方向"),
            }
        }
    }
    match convert::world_block_at(actuator, "piston") {
        Some(item) => world.push(item),
        None => return judge.fail("非法方块或方向"),
    }
    match convert::world_block_at(power, "redstone_block") {
        Some(item) => world.push(item),
        None => return judge.fail("非法方块或方向"),
    }
    {
        let positions: HashSet<Position> = world.iter().map(|item| item.position).collect();
        if positions.len() != world.len() {
            return judge.fail("初始结构、负载或外部推动装置重叠");
        }
    }

    judge.result.simulator_started = true;
    let snapshot = match judge.apply(EngineCommand::ReplaceWorld { blocks: world }) {
        Ok(view) => view,
        Err(message) => return judge.fail(&message),
    };
    if !issues.is_empty() {
        // 理论上不可达；保留结构以防后续加入运行时检查。
    }

    // 结构本体的稳定编号与初始坐标。
    let ids: HashMap<Point, BlockId> = snapshot
        .blocks
        .iter()
        .map(|block| (block.point(), block.id))
        .collect();
    let members: Vec<(BlockId, Position)> = proposal
        .blocks
        .iter()
        .filter_map(|entry| {
            ids.get(&entry.position)
                .map(|id| (*id, convert::position(entry.position)))
        })
        .collect();
    if members.len() != proposal.blocks.len() {
        return judge.fail("模拟输入不合法：结构方块编号缺失");
    }
    // 每个目标的十块负载编号与初始 z。
    let load_members: Vec<Vec<(BlockId, i32)>> = task
        .targets
        .iter()
        .map(|target| {
            (0..LOAD_BLOCKS)
                .map(|i| {
                    let point = Point::new(target.x, target.y, target.z + i as i32);
                    (ids.get(&point).copied().unwrap_or_default(), target.z + i as i32)
                })
                .collect()
        })
        .collect();

    let mut foundation = if options.foundation {
        Some(Foundation::new(&task, members.clone(), &snapshot, options.require_activation))
    } else {
        None
    };

    // max_ticks 为 0 表示无时限：每轮跑到全部目标推完就结束，只用安全上限兜底。
    let unlimited = task.max_ticks == 0;
    let limit: u64 = if unlimited {
        SAFETY_TICKS
    } else {
        task.max_ticks as u64
    };

    let mut deferred_reason: Option<String> = None;
    let mut foundation_failed = false;

    for cycle in 0..task.rounds {
        if let Some(observer) = foundation.as_mut() {
            observer.begin(cycle, &snapshot);
        }
        let mut ticks: Vec<Option<u64>> = vec![None; task.targets.len()];
        let mut moved: HashSet<BlockId> = HashSet::new();
        let mut progress_count: usize = 0;
        let mut progress_tick: u64 = 0;
        let mut cycle_snapshot = snapshot.clone();

        for tick in 1..=limit {
            cycle_snapshot = match judge.apply(EngineCommand::Step { ticks: 1 }) {
                Ok(view) => view,
                Err(message) => return judge.fail(&message),
            };
            if let Some(observer) = foundation.as_mut() {
                observer.observe(&cycle_snapshot, 1);
            }

            for (i, (target, group)) in task
                .targets
                .iter()
                .zip(load_members.iter())
                .enumerate()
            {
                let mut complete = true;
                for (block_id, start_z) in group {
                    let actual = cycle_snapshot.block(*block_id);
                    let position = actual.map(|b| b.position);
                    let matches = position.is_some_and(|p| {
                        p.x == target.x
                            && p.y == target.y
                            && (p.z == start_z + cycle || p.z == start_z + cycle + 1)
                    });
                    if !matches {
                        if !options.foundation || options.fail_fast {
                            return judge.fail("负载消失、侧移或超出一格");
                        }
                        deferred_reason
                            .get_or_insert_with(|| "负载消失、侧移或超出一格".to_string());
                    }
                    let advanced = position
                        .is_some_and(|p| p.z == start_z + cycle + 1);
                    if advanced {
                        moved.insert(*block_id);
                    } else {
                        if moved.contains(block_id) {
                            if !options.foundation || options.fail_fast {
                                return judge.fail("负载被回拉");
                            }
                            deferred_reason
                                .get_or_insert_with(|| "负载被回拉".to_string());
                        }
                        complete = false;
                    }
                }
                if complete && ticks[i].is_none() {
                    ticks[i] = Some(tick);
                }
            }

            if unlimited {
                if moved.len() > progress_count {
                    progress_count = moved.len();
                    progress_tick = tick;
                } else if tick - progress_tick > STALL_TICKS {
                    return judge.fail("连续多刻没有任何负载前进");
                }
                if ticks.iter().all(|t| t.is_some()) {
                    // 本轮目标全部推完，本轮判定到此为止，后面不再检查。
                    break;
                }
            }

            if tick == 4 {
                cycle_snapshot = match judge.apply(EngineCommand::RemoveBlock {
                    position: convert::position(power),
                }) {
                    Ok(view) => view,
                    Err(message) => return judge.fail(&message),
                };
                if let Some(observer) = foundation.as_mut() {
                    observer.observe(&cycle_snapshot, 0);
                }
            }

            if judge.started.elapsed().as_secs_f64() > TIME_LIMIT_SECONDS {
                return judge.fail("完整候选模拟达到三十秒上限");
            }
        }

        if let Some(observer) = foundation.as_mut() {
            observer.end(true);
        }

        let mut target_reason = String::new();
        if ticks.iter().any(|t| t.is_none()) {
            target_reason = if unlimited {
                "安全上限内未完成全部目标的十块负载".to_string()
            } else {
                "时限内未完成全部目标的十块负载".to_string()
            };
        } else {
            // 按完成刻排名对齐时序组。
            let mut distinct: Vec<u64> = ticks.iter().filter_map(|t| *t).collect();
            distinct.sort();
            distinct.dedup();
            let ranks: HashMap<u64, i32> = distinct
                .iter()
                .enumerate()
                .map(|(index, tick)| (*tick, index as i32 + 1))
                .collect();
            let mismatch = ticks.iter().zip(task.targets.iter()).any(|(tick, target)| {
                tick.map(|t| ranks.get(&t).copied().unwrap_or(0) != target.order)
                    .unwrap_or(true)
            });
            if mismatch {
                target_reason = "目标先后顺序或同刻分组不符合需求".to_string();
            }
        }

        // 每个目标的十块负载只要都在前进，就说明机器确实在推动负载；
        // 此时若仅时序分组或时限不合格，记作半通过，便于优先展示。
        let advanced_targets: Vec<usize> = load_members
            .iter()
            .enumerate()
            .filter(|(_, group)| group.iter().any(|(block_id, _)| moved.contains(block_id)))
            .map(|(index, _)| index)
            .collect();
        if !target_reason.is_empty() {
            if advanced_targets.len() == task.targets.len() {
                judge.result.partial = Some(true);
                if judge.result.partial_reason.is_none() {
                    judge.result.partial_reason = Some(target_reason.clone());
                }
                judge
                    .result
                    .partial_rounds
                    .get_or_insert_with(Vec::new)
                    .push(cycle + 1);
            }
            if !options.foundation || options.fail_fast {
                return judge.fail(&target_reason);
            }
            deferred_reason.get_or_insert(target_reason);
            foundation_failed = true;
        }

        // 判定标准是连续运行与按需求时序推完全部十块负载；个别方块未随行只作为诊断。
        // 期望位置是「初始 z 再加已完成轮数」：`cycle` 从 0 起，第 `cycle+1` 轮结束时
        // 方块应已前进 `cycle+1` 格。少加这一格会让所有通过的候选都被记成未随行。
        let expected_shift = cycle + 1;
        let stayed: Vec<Point> = members
            .iter()
            .filter(|(id, position)| {
                cycle_snapshot
                    .block(*id)
                    .map(|block| {
                        block.position
                            != Position::new(position.x, position.y, position.z + expected_shift)
                    })
                    .unwrap_or(true)
            })
            .map(|(_, position)| Point::new(position.x, position.y, position.z))
            .collect();
        // 两个派生值必须在 `stayed` 被移动进诊断记录之前算好。
        let translation = stayed.is_empty();
        let unmoved_count = stayed.len();
        if !translation {
            judge
                .result
                .body_diagnostics
                .get_or_insert_with(Vec::new)
                .push(BodyDiagnostic {
                    round: cycle + 1,
                    moved: members.len() - unmoved_count,
                    total: members.len(),
                    unmoved: stayed,
                });
        }

        // 只要求外部触发器能安全搬到下一轮。
        let external_ok = cycle_snapshot
            .block_at(actuator)
            .map(|block| block.is_fully_retracted())
            .unwrap_or(false);
        if !external_ok {
            return judge.fail("外部推动器在周期末未回缩");
        }

        if deferred_reason.is_none() {
            let period = if task.max_ticks != 0 {
                task.max_ticks as u64
            } else {
                ticks.iter().filter_map(|t| *t).max().unwrap_or(0)
            };
            judge.result.rounds.push(RoundOutcome {
                round: cycle + 1,
                ticks: ticks.clone(),
                period,
                translation,
            });
        }

        if cycle + 1 < task.rounds {
            if ROUND_GAP_TICKS > 0 {
                if let Err(message) = judge.apply(EngineCommand::Step {
                    ticks: ROUND_GAP_TICKS,
                }) {
                    return judge.fail(&message);
                }
            }
            // 移除旧推动器后的快照要用来检查下一轮位置是否被占，因此这里必须保留。
            let gap_snapshot = match judge.apply(EngineCommand::RemoveBlock {
                position: convert::position(actuator),
            }) {
                Ok(view) => view,
                Err(message) => return judge.fail(&message),
            };
            actuator = Point::new(actuator.x, actuator.y, actuator.z + 1);
            power = Point::new(power.x, power.y, power.z + 1);
            // 该位置被别的方块占住时按“被占用”处理，与 Python 的 blocked 集合一致。
            if gap_snapshot.is_blocked(actuator) || gap_snapshot.is_blocked(power) {
                return judge.fail("下一轮外部推动装置位置被占用");
            }
            if let Err(message) = judge.apply(EngineCommand::SetBlock {
                position: convert::position(actuator),
                block: match convert::world_block_at(actuator, "piston") {
                    Some(item) => item.block,
                    None => return judge.fail("非法方块或方向"),
                },
            }) {
                return judge.fail(&message);
            }
            // 这是本轮最后一步写入；它的快照由下一轮开始时的观测重新读取。
            if let Err(message) = judge.apply(EngineCommand::SetBlock {
                position: convert::position(power),
                block: match convert::world_block_at(power, "redstone_block") {
                    Some(item) => item.block,
                    None => return judge.fail("非法方块或方向"),
                },
            }) {
                return judge.fail(&message);
            }
        }
    }

    if let Some(reason) = deferred_reason {
        if let Some(observer) = foundation.as_mut() {
            observer.finish(&mut judge.result);
        }
        let _ = foundation_failed;
        return judge.fail(&reason);
    }

    if let Some(observer) = foundation.as_mut() {
        observer.finish(&mut judge.result);
    }
    judge.succeed()
}

/// 判定一个候选并把结果序列化为 JSON 字符串，供 JNI 直接返回。
pub fn evaluate_json(request_json: &str) -> Result<String, String> {
    let request: EvaluateRequest =
        serde_json::from_str(request_json).map_err(|error| format!("判定请求解析失败：{error}"))?;
    crate::task::validate(&request.task)?;
    // 参数校验必须在进入模拟前完成，与 Python 侧入口一致。
    let result = evaluate(&request);
    serde_json::to_string(&result).map_err(|error| format!("判定结果序列化失败：{error}"))
}

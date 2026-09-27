//! 原生运算层的数据模型。
//!
//! 字段名与 `frontend/src/features/generator/types.ts` 的游戏侧类型保持一致，
//! 因此从 Kotlin 侧传来的 JSON 可以直接反序列化，结果 JSON 也可以直接交给网页显示。

use serde::{Deserialize, Serialize};

use crate::foundation::FoundationResult;

/// 一个整数三维坐标。
#[derive(
    Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize,
)]
pub struct Point {
    pub x: i32,
    pub y: i32,
    pub z: i32,
}

impl Point {
    pub const fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }
}

/// 方块规格；种类与朝向都用引擎的序列化名。
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct BlockSpec {
    pub kind: String,
    #[serde(default = "default_facing")]
    pub facing: String,
}

fn default_facing() -> String {
    "positive_z".into()
}

/// 带坐标的方块输入。
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct BlockEntry {
    pub position: Point,
    pub block: BlockSpec,
}

/// 模型给出的候选结构。
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct Proposal {
    pub blocks: Vec<BlockEntry>,
    pub push: Point,
}

/// 单轮判定结果，对应 `evaluator.py` 里 `result["rounds"]` 的元素。
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RoundOutcome {
    pub round: i32,
    /// 每个目标的完成刻；未完成为 null，与 Python 的 None 一致。
    pub ticks: Vec<Option<u64>>,
    pub period: u64,
    pub translation: bool,
}

/// 整线随行诊断，不参与主判定。
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BodyDiagnostic {
    pub round: i32,
    pub moved: usize,
    pub total: usize,
    pub unmoved: Vec<Point>,
}

/// 回放里的一帧：一条命令加上执行后的快照。
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TraceFrame {
    pub command: serde_json::Value,
    pub snapshot: serde_json::Value,
}

/// 完整判定结果。
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Evaluation {
    pub accepted: bool,
    pub protocol: String,
    pub engine_version: String,
    pub rounds: Vec<RoundOutcome>,
    pub reason: String,
    pub load_blocks: usize,
    pub simulator_started: bool,
    pub simulated_ticks: u64,
    pub design_rule: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub partial: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub partial_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub partial_rounds: Option<Vec<i32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub body_diagnostics: Option<Vec<BodyDiagnostic>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub design_issues: Option<Vec<serde_json::Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub seconds: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trace: Option<Vec<TraceFrame>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub foundation: Option<FoundationResult>,
}

impl Evaluation {
    pub fn new(engine_version: &str) -> Self {
        Self {
            accepted: false,
            protocol: crate::protocol::PROTOCOL.into(),
            engine_version: engine_version.into(),
            rounds: Vec::new(),
            reason: String::new(),
            load_blocks: crate::protocol::LOAD_BLOCKS,
            simulator_started: false,
            simulated_ticks: 0,
            design_rule: crate::protocol::RULE.into(),
            partial: None,
            partial_reason: None,
            partial_rounds: None,
            body_diagnostics: None,
            design_issues: None,
            seconds: None,
            trace: None,
            foundation: None,
        }
    }
}

/// 判定选项，对应 `evaluator.py` 的关键字参数。
#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct Options {
    /// 是否记录逐帧回放。
    #[serde(default)]
    pub capture: bool,
    /// 是否启用整线平移与逐活塞激活观测。
    #[serde(default)]
    pub foundation: bool,
    /// 激活是否参与准入；当前标准下只作诊断。
    #[serde(default = "default_true")]
    pub require_activation: bool,
    /// 是否在 foundation 模式下提前失败。
    #[serde(default)]
    pub fail_fast: bool,
}

fn default_true() -> bool {
    true
}

impl Default for Options {
    fn default() -> Self {
        Self {
            capture: false,
            foundation: false,
            require_activation: true,
            fail_fast: false,
        }
    }
}

/// 一次判定请求：需求、候选与选项。
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EvaluateRequest {
    pub task: crate::task::Task,
    pub proposal: Proposal,
    #[serde(default)]
    pub options: Options,
}

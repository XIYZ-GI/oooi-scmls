//! 安卓端原生运算层。
//!
//! 分工：模型推理由 Kotlin 侧的 PyTorch Lite 负责，本 crate 负责红石模拟、
//! 十负载判定、领域规则与整线诊断。所有逻辑都能脱离 JNI 单独构建与测试，
//! 一致性用例正是利用这一点在宿主机上与 Python 参考实现逐字段比对。

pub mod convert;
pub mod domain_rules;
pub mod evaluator;
pub mod foundation;
pub mod model;
pub mod placement;
pub mod protocol;
pub mod task;
pub mod view;

#[cfg(feature = "jni")]
pub mod jni_bridge;

pub use evaluator::{evaluate, evaluate_json};
pub use model::{EvaluateRequest, Evaluation, Options, Proposal};
pub use task::{validate, Task};

/// 原生运算层的对外版本号。
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// 判定一个候选，输入输出都是 JSON 字符串。
///
/// 这是给非 JNI 调用方（宿主机测试、一致性验证）准备的统一入口。
pub fn judge(request_json: &str) -> Result<String, String> {
    evaluator::evaluate_json(request_json)
}

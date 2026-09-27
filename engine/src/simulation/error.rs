use thiserror::Error;

use crate::world::WorldError;

#[derive(Debug, Error)]
pub enum SimulationError {
    #[error(transparent)]
    World(#[from] WorldError),
    #[error("当前没有可恢复的检查点")]
    MissingCheckpoint,
    #[error("单次推进最多允许 1000 游戏刻")]
    StepLimitExceeded,
    #[error("命令解析失败：{0}")]
    InvalidCommand(String),
    #[error("状态序列化失败：{0}")]
    Serialization(String),
}

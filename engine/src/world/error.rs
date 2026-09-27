use crate::types::Position;
use thiserror::Error;

#[derive(Clone, Debug, Error, Eq, PartialEq)]
pub enum WorldError {
    #[error("坐标 {0:?} 已有方块")]
    Occupied(Position),
    #[error("坐标 {0:?} 没有方块")]
    Missing(Position),
    #[error("坐标 {0:?} 正在运动或被活塞臂占用")]
    Busy(Position),
    #[error("方块 {0} 不存在")]
    MissingBlock(u64),
}

use serde::{Deserialize, Serialize};

#[derive(
    Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize,
)]
#[serde(rename_all = "snake_case")]
pub enum Direction {
    PositiveX,
    NegativeX,
    PositiveY,
    NegativeY,
    #[default]
    PositiveZ,
    NegativeZ,
}

impl Direction {
    pub const ALL: [Self; 6] = [
        Self::PositiveX,
        Self::NegativeX,
        Self::PositiveY,
        Self::NegativeY,
        Self::PositiveZ,
        Self::NegativeZ,
    ];

    pub const fn vector(self) -> (i32, i32, i32) {
        match self {
            Self::PositiveX => (1, 0, 0),
            Self::NegativeX => (-1, 0, 0),
            Self::PositiveY => (0, 1, 0),
            Self::NegativeY => (0, -1, 0),
            Self::PositiveZ => (0, 0, 1),
            Self::NegativeZ => (0, 0, -1),
        }
    }

    pub const fn opposite(self) -> Self {
        match self {
            Self::PositiveX => Self::NegativeX,
            Self::NegativeX => Self::PositiveX,
            Self::PositiveY => Self::NegativeY,
            Self::NegativeY => Self::PositiveY,
            Self::PositiveZ => Self::NegativeZ,
            Self::NegativeZ => Self::PositiveZ,
        }
    }
}

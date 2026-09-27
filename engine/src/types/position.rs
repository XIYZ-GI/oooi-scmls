use serde::{Deserialize, Serialize};

use super::Direction;

#[derive(
    Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize,
)]
pub struct Position {
    pub x: i32,
    pub y: i32,
    pub z: i32,
}

impl Position {
    pub const fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }

    pub fn offset(self, direction: Direction) -> Self {
        self.translated(direction, 1)
    }

    pub fn translated(self, direction: Direction, distance: i32) -> Self {
        let (x, y, z) = direction.vector();
        Self::new(
            self.x + x * distance,
            self.y + y * distance,
            self.z + z * distance,
        )
    }
}

mod adhesion;
mod movement;
mod power;

pub use adhesion::blocks_stick;
pub use movement::{plan_movement, MovementError, MovementMode, PISTON_PUSH_LIMIT};
pub use power::{resolve_power, PowerState};

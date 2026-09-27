//! 直接构造与JSON快照同形的Python对象，避免快照克隆及文本往返。

use pyo3::{
    prelude::*,
    types::{PyDict, PyList},
};

use crate::{
    simulation::Simulator,
    types::{ObserverPhase, PistonPhase, Position},
    world::{ArmPhase, MotionKind},
};

mod names {
    use crate::{
        simulation::SimulationEventKind,
        types::{BlockKind, Direction},
    };
    pub fn kind(v: BlockKind) -> &'static str {
        match v {
            BlockKind::SlimeBlock => "slime_block",
            BlockKind::HoneyBlock => "honey_block",
            BlockKind::Piston => "piston",
            BlockKind::StickyPiston => "sticky_piston",
            BlockKind::Observer => "observer",
            BlockKind::RedstoneBlock => "redstone_block",
            BlockKind::IronBlock => "iron_block",
            BlockKind::Glass => "glass",
            BlockKind::LightBlueGlazedTerracotta => "light_blue_glazed_terracotta",
        }
    }
    pub fn direction(v: Direction) -> &'static str {
        match v {
            Direction::PositiveX => "positive_x",
            Direction::NegativeX => "negative_x",
            Direction::PositiveY => "positive_y",
            Direction::NegativeY => "negative_y",
            Direction::PositiveZ => "positive_z",
            Direction::NegativeZ => "negative_z",
        }
    }
    pub fn event(v: SimulationEventKind) -> &'static str {
        use SimulationEventKind::*;
        match v {
            BlockPlaced => "block_placed",
            BlockRemoved => "block_removed",
            WorldCleared => "world_cleared",
            WorldReplaced => "world_replaced",
            CheckpointCreated => "checkpoint_created",
            CheckpointRestored => "checkpoint_restored",
            PistonPowered => "piston_powered",
            PistonUnpowered => "piston_unpowered",
            PistonExtensionScheduled => "piston_extension_scheduled",
            PistonExtensionStarted => "piston_extension_started",
            PistonExtensionCompleted => "piston_extension_completed",
            PistonExtensionBlocked => "piston_extension_blocked",
            PistonRetractionScheduled => "piston_retraction_scheduled",
            PistonRetractionStarted => "piston_retraction_started",
            PistonRetractionCompleted => "piston_retraction_completed",
            PistonPullSkipped => "piston_pull_skipped",
            BlockMoved => "block_moved",
            ObserverPulseScheduled => "observer_pulse_scheduled",
            ObserverPulseStarted => "observer_pulse_started",
            ObserverPulseEnded => "observer_pulse_ended",
        }
    }
}

fn position(py: Python<'_>, p: Position) -> PyResult<Bound<'_, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("x", p.x)?;
    d.set_item("y", p.y)?;
    d.set_item("z", p.z)?;
    Ok(d)
}

fn piston(py: Python<'_>, phase: PistonPhase) -> PyResult<Bound<'_, PyDict>> {
    let d = PyDict::new(py);
    let name = match phase {
        PistonPhase::Retracted => "retracted",
        PistonPhase::Extended => "extended",
        PistonPhase::Blocked => "blocked",
        PistonPhase::ExtensionPending { starts_at } => {
            d.set_item("starts_at", starts_at)?;
            "extension_pending"
        }
        PistonPhase::RetractionPending { starts_at } => {
            d.set_item("starts_at", starts_at)?;
            "retraction_pending"
        }
        PistonPhase::Extending { completes_at } => {
            d.set_item("completes_at", completes_at)?;
            "extending"
        }
        PistonPhase::Retracting { completes_at } => {
            d.set_item("completes_at", completes_at)?;
            "retracting"
        }
    };
    d.set_item("phase", name)?;
    Ok(d)
}

fn observer(py: Python<'_>, phase: ObserverPhase) -> PyResult<Bound<'_, PyDict>> {
    let d = PyDict::new(py);
    let name = match phase {
        ObserverPhase::Idle => "idle",
        ObserverPhase::PulsePending { starts_at } => {
            d.set_item("starts_at", starts_at)?;
            "pulse_pending"
        }
        ObserverPhase::Pulsing { ends_at } => {
            d.set_item("ends_at", ends_at)?;
            "pulsing"
        }
    };
    d.set_item("phase", name)?;
    Ok(d)
}

pub fn snapshot(py: Python<'_>, engine: &Simulator) -> PyResult<Py<PyDict>> {
    let d = PyDict::new(py);
    d.set_item("tick", engine.tick())?;
    let blocks = PyList::empty(py);
    for (p, b) in engine.world().blocks() {
        let item = PyDict::new(py);
        item.set_item("position", position(py, *p)?)?;
        item.set_item("id", b.id)?;
        item.set_item("kind", names::kind(b.kind))?;
        item.set_item("facing", names::direction(b.facing))?;
        item.set_item("powered", b.powered)?;
        item.set_item("strongly_powered", b.strongly_powered)?;
        item.set_item(
            "piston_phase",
            b.piston_phase.map(|v| piston(py, v)).transpose()?,
        )?;
        item.set_item(
            "observer_phase",
            b.observer_phase.map(|v| observer(py, v)).transpose()?,
        )?;
        blocks.append(item)?;
    }
    d.set_item("blocks", blocks)?;
    let arms = PyList::empty(py);
    for a in engine.world().arms().values() {
        let item = PyDict::new(py);
        item.set_item("piston_id", a.piston_id)?;
        item.set_item("position", position(py, a.position)?)?;
        item.set_item("facing", names::direction(a.facing))?;
        item.set_item("sticky", a.sticky)?;
        item.set_item(
            "phase",
            match a.phase {
                ArmPhase::Extending => "extending",
                ArmPhase::Extended => "extended",
                ArmPhase::Retracting => "retracting",
            },
        )?;
        item.set_item("started_at", a.started_at)?;
        item.set_item("completes_at", a.completes_at)?;
        arms.append(item)?;
    }
    d.set_item("arms", arms)?;
    let motions = PyList::empty(py);
    for m in engine.world().motions().values() {
        let item = PyDict::new(py);
        item.set_item("piston_id", m.piston_id)?;
        item.set_item(
            "kind",
            match m.kind {
                MotionKind::Push => "push",
                MotionKind::Pull => "pull",
            },
        )?;
        item.set_item("direction", names::direction(m.direction))?;
        item.set_item("started_at", m.started_at)?;
        item.set_item("completes_at", m.completes_at)?;
        let members = PyList::empty(py);
        for b in &m.blocks {
            let member = PyDict::new(py);
            member.set_item("block_id", b.block_id)?;
            member.set_item("from", position(py, b.from)?)?;
            member.set_item("to", position(py, b.to)?)?;
            members.append(member)?;
        }
        item.set_item("blocks", members)?;
        motions.append(item)?;
    }
    d.set_item("motions", motions)?;
    let events = PyList::empty(py);
    for e in engine.events() {
        let item = PyDict::new(py);
        item.set_item("sequence", e.sequence)?;
        item.set_item("tick", e.tick)?;
        item.set_item("kind", names::event(e.kind))?;
        item.set_item("block_id", e.block_id)?;
        item.set_item("position", e.position.map(|p| position(py, p)).transpose()?)?;
        item.set_item("from", e.from.map(|p| position(py, p)).transpose()?)?;
        item.set_item("to", e.to.map(|p| position(py, p)).transpose()?)?;
        item.set_item("message", &e.message)?;
        events.append(item)?;
    }
    d.set_item("events", events)?;
    Ok(d.unbind())
}

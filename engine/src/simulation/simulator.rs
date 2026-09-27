use crate::{
    types::{BlockId, BlockSpec, Position},
    world::World,
};

use super::{
    EngineCommand, SimulationError, SimulationEvent, SimulationEventKind, SimulationSnapshot,
    WorldBlockInput,
};

pub(super) const STATE_DELAY: u64 = 2;
const MAX_EVENTS: usize = 500;

#[derive(Clone, Debug)]
pub(super) struct Checkpoint {
    pub tick: u64,
    pub world: World,
}

#[derive(Clone, Debug)]
pub struct Simulator {
    pub(super) tick: u64,
    pub(super) world: World,
    pub(super) checkpoint: Option<Checkpoint>,
    pub(super) events: Vec<SimulationEvent>,
    pub(super) next_event_sequence: u64,
}

impl Default for Simulator {
    fn default() -> Self {
        Self::new()
    }
}

impl Simulator {
    pub fn new() -> Self {
        Self {
            tick: 0,
            world: World::new(),
            checkpoint: None,
            events: Vec::new(),
            next_event_sequence: 1,
        }
    }

    pub fn tick(&self) -> u64 {
        self.tick
    }

    pub fn world(&self) -> &World {
        &self.world
    }

    pub fn snapshot(&self) -> SimulationSnapshot {
        SimulationSnapshot::from_world(self.tick, &self.world, &self.events)
    }

    pub fn apply(&mut self, command: EngineCommand) -> Result<SimulationSnapshot, SimulationError> {
        self.execute(command)?;
        Ok(self.snapshot())
    }

    /// 执行命令而不复制世界；生成验收可直接读取当前状态。
    pub fn execute(&mut self, command: EngineCommand) -> Result<(), SimulationError> {
        match command {
            EngineCommand::SetBlock { position, block } => {
                self.set_block(position, block)?;
            }
            EngineCommand::RemoveBlock { position } => self.remove_block(position)?,
            EngineCommand::ReplaceWorld { blocks } => self.replace_world(blocks)?,
            EngineCommand::ClearWorld => self.clear_world(),
            EngineCommand::CreateCheckpoint => self.create_checkpoint(),
            EngineCommand::RestoreCheckpoint => self.restore_checkpoint()?,
            EngineCommand::Step { ticks } => self.step_many(ticks)?,
        }
        Ok(())
    }

    pub fn events(&self) -> &[SimulationEvent] {
        &self.events
    }

    pub fn set_block(
        &mut self,
        position: Position,
        spec: BlockSpec,
    ) -> Result<BlockId, SimulationError> {
        let id = self.world.set(position, spec)?;
        self.record(SimulationEvent::at(
            self.tick,
            SimulationEventKind::BlockPlaced,
            Some(id),
            Some(position),
            format!("在 {position:?} 放置方块 {id}"),
        ));
        self.notify_observers_watching(position);
        self.refresh_power(true);
        Ok(id)
    }

    pub fn remove_block(&mut self, position: Position) -> Result<(), SimulationError> {
        let block = self.world.remove(position)?;
        self.record(SimulationEvent::at(
            self.tick,
            SimulationEventKind::BlockRemoved,
            Some(block.id),
            Some(position),
            format!("移除坐标 {position:?} 的方块 {}", block.id),
        ));
        self.notify_observers_watching(position);
        self.refresh_power(true);
        Ok(())
    }

    pub fn clear_world(&mut self) {
        self.world.clear();
        self.tick = 0;
        self.checkpoint = None;
        self.events.clear();
        self.record(SimulationEvent::at(
            self.tick,
            SimulationEventKind::WorldCleared,
            None,
            None,
            "世界已清空",
        ));
    }

    pub fn replace_world(&mut self, blocks: Vec<WorldBlockInput>) -> Result<(), SimulationError> {
        let mut replacement = World::new();
        for item in blocks {
            replacement.insert(item.position, item.block)?;
        }
        self.world = replacement;
        self.tick = 0;
        self.checkpoint = None;
        self.events.clear();
        self.record(SimulationEvent::at(
            self.tick,
            SimulationEventKind::WorldReplaced,
            None,
            None,
            "已载入完整世界结构",
        ));
        self.refresh_power(true);
        Ok(())
    }

    pub fn create_checkpoint(&mut self) {
        self.checkpoint = Some(Checkpoint {
            tick: self.tick,
            world: self.world.clone(),
        });
        self.record(SimulationEvent::at(
            self.tick,
            SimulationEventKind::CheckpointCreated,
            None,
            None,
            "已保存运行检查点",
        ));
    }

    pub fn restore_checkpoint(&mut self) -> Result<(), SimulationError> {
        let checkpoint = self
            .checkpoint
            .clone()
            .ok_or(SimulationError::MissingCheckpoint)?;
        self.tick = checkpoint.tick;
        self.world = checkpoint.world;
        self.events.clear();
        self.record(SimulationEvent::at(
            self.tick,
            SimulationEventKind::CheckpointRestored,
            None,
            None,
            "已恢复运行检查点",
        ));
        Ok(())
    }

    pub fn step_many(&mut self, ticks: u32) -> Result<(), SimulationError> {
        if ticks > 1000 {
            return Err(SimulationError::StepLimitExceeded);
        }
        for _ in 0..ticks {
            self.step();
        }
        Ok(())
    }

    pub(super) fn record(&mut self, mut event: SimulationEvent) {
        event.sequence = self.next_event_sequence;
        self.next_event_sequence += 1;
        self.events.push(event);
        if self.events.len() > MAX_EVENTS {
            self.events.drain(..self.events.len() - MAX_EVENTS);
        }
    }
}

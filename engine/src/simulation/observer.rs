use crate::types::{BlockId, BlockKind, ObserverPhase, Position};

use super::{simulator::STATE_DELAY, SimulationEvent, SimulationEventKind, Simulator};

impl Simulator {
    pub(super) fn end_due_observer_pulses(&mut self) {
        let due = self.observers_matching(
            |phase| matches!(phase, ObserverPhase::Pulsing { ends_at } if ends_at <= self.tick),
        );
        for observer_id in due {
            if let Some(block) = self.world.block_by_id_mut(observer_id) {
                block.observer_phase = Some(ObserverPhase::Idle);
            }
            self.record_observer_event(
                observer_id,
                SimulationEventKind::ObserverPulseEnded,
                "观察者脉冲结束",
            );
        }
    }

    pub(super) fn start_due_observer_pulses(&mut self) {
        let due = self.observers_matching(|phase| {
            matches!(phase, ObserverPhase::PulsePending { starts_at } if starts_at <= self.tick)
        });
        for observer_id in due {
            self.begin_observer_pulse(observer_id, "观察者开始输出强充能脉冲");
        }
    }

    pub(super) fn start_moved_observer_pulse(&mut self, observer_id: BlockId) {
        self.begin_observer_pulse(observer_id, "观察者被活塞移动到位并立即输出强充能脉冲");
    }

    pub(super) fn notify_observers_watching(&mut self, changed_position: Position) {
        self.notify_observers_watching_except(changed_position, None);
    }

    pub(super) fn notify_observers_watching_except(
        &mut self,
        changed_position: Position,
        excluded_observer_position: Option<Position>,
    ) {
        let observers: Vec<_> = self
            .world
            .blocks()
            .iter()
            .filter_map(|(position, block)| {
                (block.kind == BlockKind::Observer
                    && Some(*position) != excluded_observer_position
                    && position.offset(block.facing.opposite()) == changed_position)
                    .then_some(block.id)
            })
            .collect();
        for observer_id in observers {
            self.schedule_observer(observer_id, "观察端检测到方块更新");
        }
    }

    pub(super) fn schedule_observer(&mut self, observer_id: BlockId, reason: &str) {
        let is_idle = self
            .world
            .block_by_id(observer_id)
            .is_some_and(|block| matches!(block.observer_phase, Some(ObserverPhase::Idle)));
        if !is_idle {
            return;
        }
        if let Some(block) = self.world.block_by_id_mut(observer_id) {
            block.observer_phase = Some(ObserverPhase::PulsePending {
                starts_at: self.tick + STATE_DELAY,
            });
        }
        self.record_observer_event(
            observer_id,
            SimulationEventKind::ObserverPulseScheduled,
            format!("{reason}，观察者将在 2 游戏刻后输出"),
        );
    }

    fn begin_observer_pulse(&mut self, observer_id: BlockId, message: &str) {
        if let Some(block) = self.world.block_by_id_mut(observer_id) {
            block.observer_phase = Some(ObserverPhase::Pulsing {
                ends_at: self.tick + STATE_DELAY,
            });
        }
        self.record_observer_event(
            observer_id,
            SimulationEventKind::ObserverPulseStarted,
            message,
        );
        if let Some(position) = self.world.block_position(observer_id) {
            self.notify_observers_watching(position);
        }
    }

    fn observers_matching(&self, predicate: impl Fn(ObserverPhase) -> bool) -> Vec<BlockId> {
        self.world
            .block_ids()
            .into_iter()
            .filter(|id| {
                self.world
                    .block_by_id(*id)
                    .and_then(|block| block.observer_phase)
                    .is_some_and(&predicate)
            })
            .collect()
    }

    fn record_observer_event(
        &mut self,
        observer_id: BlockId,
        kind: SimulationEventKind,
        message: impl Into<String>,
    ) {
        self.record(SimulationEvent::at(
            self.tick,
            kind,
            Some(observer_id),
            self.world.block_position(observer_id),
            message,
        ));
    }
}

use crate::{
    types::{BlockId, BlockKind, PistonPhase},
    world::{ArmPhase, Motion, PistonArm},
};

use super::{simulator::STATE_DELAY, SimulationEvent, SimulationEventKind, Simulator};

impl Simulator {
    pub fn step(&mut self) {
        self.tick += 1;
        let topology_changed = self.complete_due_motions();
        self.end_due_observer_pulses();
        self.start_due_observer_pulses();
        self.start_due_piston_actions();
        self.refresh_power(topology_changed);
    }

    fn complete_due_motions(&mut self) -> bool {
        let due: Vec<_> = self
            .world
            .block_ids()
            .into_iter()
            .filter(|id| {
                self.world.block_by_id(*id).is_some_and(|block| {
                    matches!(
                        block.piston_phase,
                        Some(PistonPhase::Extending { completes_at })
                            | Some(PistonPhase::Retracting { completes_at })
                            if completes_at <= self.tick
                    )
                })
            })
            .collect();
        let mut topology_changed = false;
        for piston_id in due {
            topology_changed |= self.complete_piston_motion(piston_id);
        }
        topology_changed
    }

    fn complete_piston_motion(&mut self, piston_id: BlockId) -> bool {
        let Some(phase) = self
            .world
            .block_by_id(piston_id)
            .and_then(|block| block.piston_phase)
        else {
            return false;
        };
        let Ok(motion) = self.world.complete_motion(piston_id) else {
            return false;
        };
        let topology_changed =
            !motion.blocks.is_empty() || matches!(phase, PistonPhase::Retracting { .. });

        match phase {
            PistonPhase::Extending { .. } => self.finish_extension(piston_id),
            PistonPhase::Retracting { .. } => self.finish_retraction(piston_id),
            _ => return false,
        }
        self.handle_completed_block_moves(&motion);
        self.schedule_follow_up_action(piston_id, phase);
        topology_changed
    }

    fn finish_extension(&mut self, piston_id: BlockId) {
        if let Some(block) = self.world.block_by_id_mut(piston_id) {
            block.piston_phase = Some(PistonPhase::Extended);
        }
        if let Some(position) = self.world.block_position(piston_id) {
            let piston = self.world.block_by_id(piston_id).expect("活塞必须存在");
            self.world.set_arm(
                piston_id,
                PistonArm {
                    piston_id,
                    position: position.offset(piston.facing),
                    facing: piston.facing,
                    sticky: piston.kind.is_sticky_piston(),
                    phase: ArmPhase::Extended,
                    started_at: self.tick,
                    completes_at: None,
                },
            );
        }
        self.record_piston_event(
            piston_id,
            SimulationEventKind::PistonExtensionCompleted,
            "活塞伸出完成",
        );
    }

    fn finish_retraction(&mut self, piston_id: BlockId) {
        let arm_position = self.world.arms().get(&piston_id).map(|arm| arm.position);
        self.world.remove_arm(piston_id);
        if let Some(block) = self.world.block_by_id_mut(piston_id) {
            block.piston_phase = Some(PistonPhase::Retracted);
        }
        self.record_piston_event(
            piston_id,
            SimulationEventKind::PistonRetractionCompleted,
            "活塞收回完成",
        );
        if let Some(position) = arm_position {
            self.notify_observers_watching(position);
        }
    }

    fn schedule_follow_up_action(&mut self, piston_id: BlockId, completed: PistonPhase) {
        let powered = self
            .world
            .block_by_id(piston_id)
            .is_some_and(|block| block.powered);
        let next_phase = match (completed, powered) {
            (PistonPhase::Extending { .. }, false) => Some((
                PistonPhase::RetractionPending {
                    starts_at: self.tick + STATE_DELAY,
                },
                SimulationEventKind::PistonRetractionScheduled,
                "活塞已安排收回",
            )),
            (PistonPhase::Retracting { .. }, true) => Some((
                PistonPhase::ExtensionPending {
                    starts_at: self.tick + STATE_DELAY,
                },
                SimulationEventKind::PistonExtensionScheduled,
                "活塞已重新安排伸出",
            )),
            _ => None,
        };
        if let Some((phase, kind, message)) = next_phase {
            if let Some(block) = self.world.block_by_id_mut(piston_id) {
                block.piston_phase = Some(phase);
            }
            self.record_piston_event(piston_id, kind, message);
        }
    }

    fn handle_completed_block_moves(&mut self, motion: &Motion) {
        for item in &motion.blocks {
            let moved_observer_watches = self.world.block_by_id(item.block_id).and_then(|block| {
                (block.kind == BlockKind::Observer)
                    .then_some(item.to.offset(block.facing.opposite()))
            });
            self.record(SimulationEvent::movement(
                self.tick,
                item.block_id,
                item.from,
                item.to,
            ));
            self.notify_observers_watching(item.from);
            if let Some(watched_position) = moved_observer_watches {
                // 互相正对时由移动观察者的即时输出初始化时钟，避免固定侧因入位更新提前激活。
                self.notify_observers_watching_except(item.to, Some(watched_position));
                self.start_moved_observer_pulse(item.block_id);
            } else {
                self.notify_observers_watching(item.to);
            }
        }
    }

    fn start_due_piston_actions(&mut self) {
        for piston_id in self.world.block_ids() {
            let phase = self
                .world
                .block_by_id(piston_id)
                .and_then(|block| block.piston_phase);
            match phase {
                Some(PistonPhase::ExtensionPending { starts_at }) if starts_at <= self.tick => {
                    self.start_extension(piston_id);
                }
                Some(PistonPhase::RetractionPending { starts_at }) if starts_at <= self.tick => {
                    self.start_retraction(piston_id);
                }
                _ => {}
            }
        }
    }
}

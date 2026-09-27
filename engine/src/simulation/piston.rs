use crate::{
    mechanics::{plan_movement, resolve_power, MovementMode},
    types::{BlockId, Direction, PistonPhase, Position},
    world::{ArmPhase, Motion, MotionKind, PistonArm},
};

use super::{simulator::STATE_DELAY, SimulationEvent, SimulationEventKind, Simulator};

impl Simulator {
    pub(super) fn start_extension(&mut self, piston_id: BlockId) {
        let Some((position, facing, sticky, powered)) = self.piston_details(piston_id) else {
            return;
        };
        if !powered {
            if let Some(block) = self.world.block_by_id_mut(piston_id) {
                block.piston_phase = Some(PistonPhase::Retracted);
            }
            return;
        }

        let blocks = match plan_movement(
            &self.world,
            position.offset(facing),
            facing,
            MovementMode::Push,
            piston_id,
        ) {
            Ok(blocks) => blocks,
            Err(error) => {
                if let Some(block) = self.world.block_by_id_mut(piston_id) {
                    block.piston_phase = Some(PistonPhase::Blocked);
                }
                self.record_piston_event(
                    piston_id,
                    SimulationEventKind::PistonExtensionBlocked,
                    format!("活塞无法伸出：{error}"),
                );
                return;
            }
        };

        let completes_at = self.tick + STATE_DELAY;
        let arm_position = position.offset(facing);
        self.world.add_motion(
            Motion {
                piston_id,
                kind: MotionKind::Push,
                direction: facing,
                started_at: self.tick,
                completes_at,
                blocks,
            },
            PistonArm {
                piston_id,
                position: arm_position,
                facing,
                sticky,
                phase: ArmPhase::Extending,
                started_at: self.tick,
                completes_at: Some(completes_at),
            },
        );
        if let Some(block) = self.world.block_by_id_mut(piston_id) {
            block.piston_phase = Some(PistonPhase::Extending { completes_at });
        }
        self.record_piston_event(
            piston_id,
            SimulationEventKind::PistonExtensionStarted,
            "活塞开始伸出并产生活塞臂",
        );
        self.notify_observers_watching(arm_position);
    }

    pub(super) fn start_retraction(&mut self, piston_id: BlockId) {
        let Some((position, facing, sticky, powered)) = self.piston_details(piston_id) else {
            return;
        };
        if powered {
            if let Some(block) = self.world.block_by_id_mut(piston_id) {
                block.piston_phase = Some(PistonPhase::Extended);
            }
            return;
        }

        let pull_direction = facing.opposite();
        let blocks = if sticky {
            match plan_movement(
                &self.world,
                position.translated(facing, 2),
                pull_direction,
                MovementMode::Pull,
                piston_id,
            ) {
                Ok(blocks) => blocks,
                Err(error) => {
                    self.record_piston_event(
                        piston_id,
                        SimulationEventKind::PistonPullSkipped,
                        format!("粘性活塞本次未拉回方块：{error}"),
                    );
                    Vec::new()
                }
            }
        } else {
            Vec::new()
        };

        let completes_at = self.tick + STATE_DELAY;
        self.world.add_motion(
            Motion {
                piston_id,
                kind: MotionKind::Pull,
                direction: pull_direction,
                started_at: self.tick,
                completes_at,
                blocks,
            },
            PistonArm {
                piston_id,
                position: position.offset(facing),
                facing,
                sticky,
                phase: ArmPhase::Retracting,
                started_at: self.tick,
                completes_at: Some(completes_at),
            },
        );
        if let Some(block) = self.world.block_by_id_mut(piston_id) {
            block.piston_phase = Some(PistonPhase::Retracting { completes_at });
        }
        self.record_piston_event(
            piston_id,
            SimulationEventKind::PistonRetractionStarted,
            "活塞开始收回",
        );
    }

    pub(super) fn refresh_power(&mut self, topology_changed: bool) {
        let power = resolve_power(&self.world);
        for id in self.world.block_ids() {
            if let Some(position) = self.world.block_position(id) {
                if let Some(block) = self.world.block_by_id_mut(id) {
                    block.strongly_powered = power.strongly_powered.contains(&position);
                }
            }
        }

        let mut changed = Vec::new();
        let mut blocked_retries = Vec::new();
        for piston_id in self.world.block_ids() {
            let Some(block) = self.world.block_by_id(piston_id) else {
                continue;
            };
            if !block.kind.is_piston() {
                continue;
            }
            let new_powered = power.powered_pistons.contains(&piston_id);
            if block.powered != new_powered {
                changed.push((piston_id, new_powered));
            } else if topology_changed
                && new_powered
                && matches!(block.piston_phase, Some(PistonPhase::Blocked))
            {
                blocked_retries.push(piston_id);
            }
        }
        for piston_id in blocked_retries {
            if let Some(block) = self.world.block_by_id_mut(piston_id) {
                block.piston_phase = Some(PistonPhase::ExtensionPending {
                    starts_at: self.tick + STATE_DELAY,
                });
            }
            self.record_piston_event(
                piston_id,
                SimulationEventKind::PistonExtensionScheduled,
                "推动条件发生变化，持续供电的受阻活塞已重新安排伸出",
            );
        }
        for (piston_id, powered) in changed {
            self.apply_piston_power_change(piston_id, powered);
        }
    }

    fn apply_piston_power_change(&mut self, piston_id: BlockId, powered: bool) {
        let position = self.world.block_position(piston_id);
        let phase = self
            .world
            .block_by_id(piston_id)
            .and_then(|block| block.piston_phase);
        if let Some(block) = self.world.block_by_id_mut(piston_id) {
            block.powered = powered;
            block.piston_phase = match (powered, phase) {
                (true, Some(PistonPhase::Retracted | PistonPhase::Blocked)) => {
                    Some(PistonPhase::ExtensionPending {
                        starts_at: self.tick + STATE_DELAY,
                    })
                }
                (true, Some(PistonPhase::RetractionPending { .. })) => Some(PistonPhase::Extended),
                (false, Some(PistonPhase::ExtensionPending { .. })) => Some(PistonPhase::Retracted),
                (false, Some(PistonPhase::Extended)) => Some(PistonPhase::RetractionPending {
                    starts_at: self.tick + STATE_DELAY,
                }),
                (false, Some(PistonPhase::Blocked)) => Some(PistonPhase::Retracted),
                (_, current) => current,
            };
        }

        let (kind, message) = if powered {
            (SimulationEventKind::PistonPowered, "活塞收到普通红石信号")
        } else {
            (SimulationEventKind::PistonUnpowered, "活塞失去普通红石信号")
        };
        self.record(SimulationEvent::at(
            self.tick,
            kind,
            Some(piston_id),
            position,
            message,
        ));
        if let Some(position) = position {
            self.notify_observers_watching(position);
        }
        match self
            .world
            .block_by_id(piston_id)
            .and_then(|block| block.piston_phase)
        {
            Some(PistonPhase::ExtensionPending { .. }) => self.record_piston_event(
                piston_id,
                SimulationEventKind::PistonExtensionScheduled,
                "活塞已安排伸出",
            ),
            Some(PistonPhase::RetractionPending { .. }) => self.record_piston_event(
                piston_id,
                SimulationEventKind::PistonRetractionScheduled,
                "活塞已安排收回",
            ),
            _ => {}
        }
    }

    fn piston_details(&self, piston_id: BlockId) -> Option<(Position, Direction, bool, bool)> {
        let position = self.world.block_position(piston_id)?;
        let block = self.world.block_by_id(piston_id)?;
        Some((
            position,
            block.facing,
            block.kind.is_sticky_piston(),
            block.powered,
        ))
    }

    pub(super) fn record_piston_event(
        &mut self,
        piston_id: BlockId,
        kind: SimulationEventKind,
        message: impl Into<String>,
    ) {
        self.record(SimulationEvent::at(
            self.tick,
            kind,
            Some(piston_id),
            self.world.block_position(piston_id),
            message,
        ));
    }
}

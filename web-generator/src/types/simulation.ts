/** 生成器页面用到的引擎快照类型。
 *
 * 完整项目里还有模拟工作台用到的编辑器、命令与工具类型；套壳网页只负责生成结果的
 * 显示与回放，因此这里只保留绘制快照所必需的字段，形状与引擎返回的快照严格一致。
 */

export type BlockKind =
  | 'slime_block'
  | 'honey_block'
  | 'piston'
  | 'sticky_piston'
  | 'redstone_block'
  | 'observer'
  | 'iron_block'
  | 'light_blue_glazed_terracotta'
  | 'glass'

export type Direction =
  | 'positive_x'
  | 'negative_x'
  | 'positive_y'
  | 'negative_y'
  | 'positive_z'
  | 'negative_z'

export interface Position {
  x: number
  y: number
  z: number
}

export interface BlockSpec {
  kind: BlockKind
  facing: Direction
}

/** 活塞在快照里的阶段；带时间字段的中间态由引擎按需补充。 */
export type PistonPhase =
  | 'retracted'
  | 'extension_pending'
  | 'extending'
  | 'extended'
  | 'retraction_pending'
  | 'retracting'
  | 'blocked'

export interface PistonPhaseState {
  phase: PistonPhase
  starts_at?: number
  completes_at?: number
}

export interface ObserverPhaseState {
  phase: 'idle' | 'pulse_pending' | 'pulsing'
  starts_at?: number
  ends_at?: number
}

export interface PlacedBlock {
  position: Position
  id: number
  kind: BlockKind
  facing: Direction
  powered: boolean
  strongly_powered: boolean
  piston_phase: PistonPhaseState | null
  observer_phase: ObserverPhaseState | null
}

export interface PistonArmState {
  piston_id: number
  position: Position
  facing: Direction
  sticky: boolean
  phase: 'extending' | 'extended' | 'retracting'
  started_at: number
  completes_at: number | null
}

export interface MotionState {
  piston_id: number
  kind: 'push' | 'pull'
  direction: Direction
  started_at: number
  completes_at: number
  blocks: { block_id: number; from: Position; to: Position }[]
}

export interface SimulationEvent {
  sequence: number
  tick: number
  kind: string
  block_id: number | null
  position: Position | null
  from: Position | null
  to: Position | null
  message: string
}

export interface SimulationSnapshot {
  tick: number
  blocks: PlacedBlock[]
  arms: PistonArmState[]
  motions: MotionState[]
  events: SimulationEvent[]
}

export type WorldBlockInput = { position: Position; block: BlockSpec }

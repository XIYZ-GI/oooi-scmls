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

export interface PhaseState {
  phase: string
  starts_at?: number
  completes_at?: number
  ends_at?: number
}

export interface PlacedBlock extends BlockSpec {
  id: number
  position: Position
  powered: boolean
  strongly_powered: boolean
  piston_phase: PhaseState | null
  observer_phase: PhaseState | null
}

export interface MovingBlock {
  block_id: number
  from: Position
  to: Position
}

export interface MotionState {
  piston_id: number
  kind: 'push' | 'pull'
  direction: Direction
  started_at: number
  completes_at: number
  blocks: MovingBlock[]
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

export type EngineCommand =
  | { type: 'set_block'; position: Position; block: BlockSpec }
  | { type: 'remove_block'; position: Position }
  | { type: 'replace_world'; blocks: WorldBlockInput[] }
  | { type: 'clear_world' }
  | { type: 'create_checkpoint' }
  | { type: 'restore_checkpoint' }
  | { type: 'step'; ticks: number }

export type EditorTool = BlockKind | 'inspect' | 'erase'


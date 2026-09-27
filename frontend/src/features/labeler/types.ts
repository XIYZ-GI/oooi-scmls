import type { BlockKind, Direction, Position } from '@/types'

export interface ImportedBlock {
  position: Position
  name: string
  states: Record<string, string | number | boolean>
  layer: number
  kind: BlockKind | null
  facing: Direction
}

export interface TargetPoint {
  x: number
  y: number
  z: number
}

export interface TimingResult {
  status: 'success' | 'failed'
  reason: string
  targets: TimingTarget[]
  replay?: { id: string; frameCount: number }
  loadBlocks: number
  simulatedTicks: number
  maxTicks: number
  pulseTicks: number
  protocol: string
  engineVersion: string
  computedAt: string
}

export interface TimingTarget extends TargetPoint {
  tick: number | null
  order: number | null
  movedBlocks: number
  failed?: boolean
  error?: string
}

export interface LabelSample {
  id: string
  revision: number
  originals?: Array<{ id: string; filename: string; sha256: string; size: number }>
  name: string
  fileName: string
  sourceSize: [number, number, number]
  sourceOrigin: [number, number, number]
  blocks: ImportedBlock[]
  forward: Direction
  pushPoint: { x: number; y: number; z?: number } | null
  targets: TargetPoint[]
  timing: TimingResult | null
  author: string
  notes: string
  completed: boolean
  updatedAt: string
}

export interface NormalizedStructure {
  blocks: ImportedBlock[]
  width: number
  height: number
  depth: number
}

export type MarkTool = 'target' | 'push' | 'erase'

export interface ImportFailure {
  file: string
  reason: string
}

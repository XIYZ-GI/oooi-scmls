import type { Position, WorldBlockInput } from '@/types'

export interface SearchSeed {
  id: string
  name: string
  revision: number
  width: number
  height: number
  depth: number
  group: string
  split: 'train' | 'validation' | 'test'
  blocks: number
  targets: number
  attempted: number
  accepted: number
  improved: number
}

export interface SearchJob {
  id: string
  name: string
  state: string
  error: string
  config: { per_seed: number; rounds: number; random_seed: number }
  seeds: SearchSeed[]
  model: null | {
    status: string
    label: string
    trainRows: number
    positive: number
    negative: number
    reason?: string
    external?: boolean
    validation?: { rows: number; positive: number; accuracy: number; majorityBaseline: number }
  }
}

export interface Candidate {
  id: number
  job_id: string
  seed_id: string
  parent_id: number | null
  depth: number
  block_count: number
  accepted: number
  improved: number
  edit: { label: string }
  result: {
    reason: string
    load_pass: boolean
    rounds: Array<{ round: number; ticks: number; translation_pass: boolean }>
  }
}

export interface CandidateDetail {
  candidate: Candidate & { blocks: WorldBlockInput[]; push: Position }
  seed: SearchSeed & { request: { blocks: WorldBlockInput[]; push_point: Position; targets: Position[] } }
}

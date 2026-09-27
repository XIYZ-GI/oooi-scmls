import type { Position, SimulationSnapshot, WorldBlockInput } from '@/types'

export interface Target extends Position { order: number }
export interface Task {
  width: number; height: number; depth: number; targets: Target[]
  max_ticks: number; rounds: number; load_blocks: number
}
export interface Draft { model_id?: string | null; task: Task; group_count: number; revision: number; candidate_count: number }
export interface Proposal { blocks: WorldBlockInput[]; push: Position }
export interface Evaluation {
  accepted: boolean; reason: string
  /** 半通过：负载确实被推动，但时序分组或时限不满足要求。 */
  partial?: boolean
  partial_reason?: string
  foundation?: { translation: boolean; activation: boolean; accepted: boolean; piston_count: number }
  rounds: { round: number; ticks: number[]; period: number; translation: boolean }[]
}
export interface Result {
  task: Task; proposals: Proposal[]; evaluations: Evaluation[]; selected: number; accepted: boolean
  partial?: boolean
  /** 每个候选按本列最前方方块 +2 摆放负载后的需求，用于预览、回放与导出。 */
  load_tasks?: Task[]
  model_id?: string; model_name?: string; architecture?: string
  checkpoint_sha256: string; sampling_protocol: string; device: string; candidate_budget: number
}
export interface Job {
  id: string; model_id: string; name: string; task: Task; status: 'queued' | 'running' | 'success' | 'not_found' | 'cancelled' | 'error'
  progress: number; message: string; created_at: string; updated_at: string; candidate_count: number
  result?: Result | null
}
export interface Replay extends Evaluation { trace: { snapshot: SimulationSnapshot }[] }
/** 该版本模型真正读取的需求字段；缺省视为全部读取（旧版本权重）。 */
export interface ModelConditioning {
  size: boolean; targets: boolean
  max_ticks: boolean; rounds: boolean; load_blocks: boolean
  target_z?: boolean
}
export interface ModelInfo {
  id: string; status?: string; name: string; ready: boolean; parameters: number; device: string
  conditioning?: ModelConditioning
}

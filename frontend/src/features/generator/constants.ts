import type { Task } from './types'

export const DEFAULT_TASK: Task = { width: 7, height: 5, depth: 2, targets: [], max_ticks: 48, rounds: 3, load_blocks: 10 }
export const DEFAULT_CANDIDATES = 8
export const MAX_CANDIDATES = 64
export const GROUP_COLORS = ['#72b6d4', '#80b8a0', '#d5ad70', '#c28e85', '#8cacc2', '#c0b77b', '#8ebabc', '#bb9e8d']
export const BUTTON = 'inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-md border border-ink/15 bg-white px-2 text-xs text-ink/80 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-40'
export const ICON_BUTTON = BUTTON+' w-8 px-0'
export const FIELD = 'h-8 w-full min-w-0 rounded-md border border-ink/20 bg-white px-2 text-sm outline-none focus:border-sky-500'
export const STATUS = { queued: '排队中', running: '生成中', success: '通过', not_found: '未通过', cancelled: '已取消', error: '出错' }
export const busyJob = (status: string) => status === 'queued' || status === 'running'
export const groupColor = (group: number) => GROUP_COLORS[(group-1) % GROUP_COLORS.length]

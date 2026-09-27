import type { Direction } from '@/types'

export const MAX_FILE_BYTES = 16 * 1024 * 1024
export const MAX_BLOCKS = 4096
export const MAX_VOLUME = 262144
export const MAX_AXIS = 128
export const DATASET_FORMAT = 'mcscai-labels'
export const DATASET_VERSION = 1
export const DATABASE_NAME = 'mcscai-labeler-v1'
export const TARGET_LOAD_BLOCKS = 10
export const LOAD_TIMING_PROTOCOL = 'single_push_load10_v2'
export const MAX_TARGET_Z = 128
export const COMPACT_TOOL_CLASS = 'inline-flex h-8 w-8 min-w-0 shrink items-center justify-center rounded-md border border-ink/15 bg-white text-ink/70 hover:bg-sky-50 disabled:opacity-40'
export const FIELD_CLASS =
  'h-10 w-full min-w-0 rounded-md border border-ink/20 bg-white px-2 text-sm outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500'
export const BUTTON_CLASS =
  'inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-ink/20 bg-white px-3 text-sm hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-40'
export const BEDROCK_DIRECTIONS: Direction[] = [
  'negative_y',
  'positive_y',
  'negative_z',
  'positive_z',
  'negative_x',
  'positive_x',
]
export const BEDROCK_PISTON_DIRECTIONS: Direction[] = [
  'negative_y',
  'positive_y',
  'positive_z',
  'negative_z',
  'positive_x',
  'negative_x',
]

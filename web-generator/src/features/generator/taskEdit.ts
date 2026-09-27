import type { Task } from './types'

export const GRID_LIMIT = { min: 1, max: 15 }
export const DEPTH_LIMIT = { min: 2, max: 9 }
export const VOLUME_LIMIT = 512

export function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, Math.trunc(value) || min))
}

/**
 * 改变网格尺寸：越界的目标点会被丢弃，宽×高×厚度超过服务端上限时返回 null。
 * 输入框与画布边缘拖动共用这一处规则，避免两套判断不一致。
 * anchor 为 start 时另一边固定（从左/下边拖动），目标点坐标同步平移，网格朝拖动方向生长。
 */
export function resizeTask(task: Task, changes: Partial<Pick<Task, 'width' | 'height' | 'depth'>>,
                           anchor: 'start' | 'end' = 'end'): Task | null {
  const next = {
    ...task,
    width: clamp(changes.width ?? task.width, GRID_LIMIT.min, GRID_LIMIT.max),
    height: clamp(changes.height ?? task.height, GRID_LIMIT.min, GRID_LIMIT.max),
    depth: clamp(changes.depth ?? task.depth, DEPTH_LIMIT.min, DEPTH_LIMIT.max),
  }
  if (next.width * next.height * next.depth > VOLUME_LIMIT) return null
  const shiftX = anchor === 'start' && changes.width !== undefined ? next.width - task.width : 0
  const shiftY = anchor === 'start' && changes.height !== undefined ? next.height - task.height : 0
  next.targets = task.targets
    .map(target => ({ ...target, x: target.x + shiftX, y: target.y + shiftY }))
    .filter(target => target.x >= 0 && target.y >= 0 && target.x < next.width && target.y < next.height)
  return next
}

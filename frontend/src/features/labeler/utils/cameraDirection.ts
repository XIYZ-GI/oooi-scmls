import type { Direction, Position } from '@/types'
import { rotateDirection } from './coordinates'

const AXIS_DIRECTIONS: Direction[] = [
  'positive_x', 'negative_x', 'positive_y', 'negative_y', 'positive_z', 'negative_z',
]

export function directionFromCamera(vector: Position, currentForward: Direction): Direction {
  // 镜头向场景内看的方向；取绝对分量最大的轴，避免斜视产生斜向推动。
  const axes = ['x', 'y', 'z'] as const
  const axis = axes.reduce((best, candidate) => Math.abs(vector[candidate]) > Math.abs(vector[best]) ? candidate : best)
  const displayedDirection: Direction = `${vector[axis] >= 0 ? 'positive' : 'negative'}_${axis}`
  // 画面已经按旧前进方向旋转过，保存前换回原始结构坐标系。
  return AXIS_DIRECTIONS.find((direction) => rotateDirection(direction, currentForward) === displayedDirection)!
}

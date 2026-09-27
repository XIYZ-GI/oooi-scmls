import type { NormalizedStructure, TargetPoint } from '../types'

export function columnFront(shape: NormalizedStructure, point: Pick<TargetPoint, 'x' | 'y'>): number {
  const column = shape.blocks.filter((block) => block.position.x === point.x && block.position.y === point.y)
  return column.length ? Math.max(...column.map((block) => block.position.z)) : -2
}

export function defaultTargetDepth(shape: NormalizedStructure, point: Pick<TargetPoint, 'x' | 'y'>): number {
  return columnFront(shape, point) + 2
}

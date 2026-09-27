import type { NormalizedStructure } from '../types'

export function columnRear(shape: NormalizedStructure, point: { x: number; y: number }): number | null {
  const column = shape.blocks.filter((block) => block.position.x === point.x && block.position.y === point.y)
  if (!column.length) return null
  const rear = Math.min(...column.map((block) => block.position.z))
  return column.some((block) => block.layer === 0 && block.position.z === rear) ? rear : null
}

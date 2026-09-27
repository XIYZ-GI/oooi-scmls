import type { Direction, Position } from '@/types'
import type { LabelSample, NormalizedStructure } from '../types'
import { columnFront } from './targetDepth'
import { columnRear } from './pushDepth'
import { MAX_TARGET_Z } from '../constants'

const VECTORS: Record<Direction, Position> = {
  positive_x: { x: 1, y: 0, z: 0 },
  negative_x: { x: -1, y: 0, z: 0 },
  positive_y: { x: 0, y: 1, z: 0 },
  negative_y: { x: 0, y: -1, z: 0 },
  positive_z: { x: 0, y: 0, z: 1 },
  negative_z: { x: 0, y: 0, z: -1 },
}

export function rotatePosition(
  { x, y, z }: Position,
  forward: Direction,
): Position {
  switch (forward) {
    case 'positive_z':
      return { x, y, z }
    case 'negative_z':
      return { x: -x, y, z: -z }
    case 'positive_x':
      return { x: -z, y, z: x }
    case 'negative_x':
      return { x: z, y, z: -x }
    case 'positive_y':
      return { x, y: -z, z: y }
    case 'negative_y':
      return { x, y: z, z: -y }
  }
}

export function rotateDirection(
  direction: Direction,
  forward: Direction,
): Direction {
  const vector = rotatePosition(VECTORS[direction], forward)
  return (Object.keys(VECTORS) as Direction[]).find((key) => {
    const value = VECTORS[key]
    return value.x === vector.x && value.y === vector.y && value.z === vector.z
  })!
}

export function normalizeStructure(
  sample: Pick<LabelSample, 'blocks' | 'forward'>,
): NormalizedStructure {
  const rotated = sample.blocks.map((block) => ({
    ...block,
    position: rotatePosition(block.position, sample.forward),
    facing: rotateDirection(block.facing, sample.forward),
  }))
  const xs = rotated.map((block) => block.position.x)
  const ys = rotated.map((block) => block.position.y)
  const zs = rotated.map((block) => block.position.z)
  const minX = Math.min(...xs),
    minY = Math.min(...ys),
    minZ = Math.min(...zs)
  const maxZ = Math.max(...zs)
  return {
    width: Math.max(...xs) - minX + 1,
    height: Math.max(...ys) - minY + 1,
    depth: maxZ - minZ + 1,
    blocks: rotated.map((block) => ({
      ...block,
      position: {
        x: block.position.x - minX,
        y: block.position.y - minY,
        z: block.position.z - maxZ - 2,
      },
    })),
  }
}

export function annotationError(sample: LabelSample): string | null {
  if (!sample.pushPoint) return '请标注一个推动点'
  if (!sample.targets.length) return '请至少标注一个被推动的目标点'
  const shape = normalizeStructure(sample)
  for (const point of sample.targets) {
    const z = point.z ?? 0
    if (!Number.isInteger(z) || z <= columnFront(shape, point) || z > MAX_TARGET_Z) {
      return `目标 (${point.x}, ${point.y}) 的负载位置无效，请调整到该列方块前方`
    }
  }
  const rear = columnRear(shape, sample.pushPoint)
  if (rear === null) return '此位置没有可从后方接触的移动线方块'
  if (sample.pushPoint.z != null && sample.pushPoint.z !== rear) return '这个方块后方还有方块，不能作为推动点'
  return null
}

import { Quaternion, Vector3 } from 'three'

import type { Direction, PlacedBlock, Position } from '@/types'

const DIRECTION_VECTORS: Record<Direction, [number, number, number]> = {
  positive_x: [1, 0, 0],
  negative_x: [-1, 0, 0],
  positive_y: [0, 1, 0],
  negative_y: [0, -1, 0],
  positive_z: [0, 0, 1],
  negative_z: [0, 0, -1],
}

const OPPOSITE_DIRECTIONS: Record<Direction, Direction> = {
  positive_x: 'negative_x',
  negative_x: 'positive_x',
  positive_y: 'negative_y',
  negative_y: 'positive_y',
  positive_z: 'negative_z',
  negative_z: 'positive_z',
}

export function directionVector(direction: Direction): Vector3 {
  return new Vector3(...DIRECTION_VECTORS[direction])
}

export function oppositeDirection(direction: Direction): Direction {
  return OPPOSITE_DIRECTIONS[direction]
}

export function directionQuaternion(direction: Direction): Quaternion {
  return new Quaternion().setFromUnitVectors(
    new Vector3(0, 0, 1),
    directionVector(direction),
  )
}

export function addPosition(position: Position, delta: Vector3): Position {
  return {
    x: position.x + Math.round(delta.x),
    y: position.y + Math.round(delta.y),
    z: position.z + Math.round(delta.z),
  }
}

export function samePosition(left: Position | null, right: Position): boolean {
  return !!left && left.x === right.x && left.y === right.y && left.z === right.z
}

export function motionPosition(
  block: PlacedBlock,
  tick: number,
  motions: Array<{
    started_at: number
    completes_at: number
    blocks: Array<{ block_id: number; from: Position; to: Position }>
  }>,
): [number, number, number] {
  for (const motion of motions) {
    const moving = motion.blocks.find((item) => item.block_id === block.id)
    if (!moving) continue
    const duration = Math.max(1, motion.completes_at - motion.started_at)
    const progress = Math.min(1, Math.max(0, (tick - motion.started_at) / duration))
    return new Vector3(moving.from.x, moving.from.y, moving.from.z)
      .lerp(new Vector3(moving.to.x, moving.to.y, moving.to.z), progress)
      .toArray()
  }
  return [block.position.x, block.position.y, block.position.z]
}

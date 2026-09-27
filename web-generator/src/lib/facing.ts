import { Quaternion, Vector3 } from 'three'

import type { Direction } from '@/types'

/** 六个朝向对应的单位向量，供放置与旋转计算使用。 */
const VECTORS: Record<Direction, [number, number, number]> = {
  positive_x: [1, 0, 0],
  negative_x: [-1, 0, 0],
  positive_y: [0, 1, 0],
  negative_y: [0, -1, 0],
  positive_z: [0, 0, 1],
  negative_z: [0, 0, -1],
}

const AXES: Array<[keyof typeof VECTORS, [number, number, number]]> = [
  ['positive_x', [1, 0, 0]],
  ['negative_x', [-1, 0, 0]],
  ['positive_y', [0, 1, 0]],
  ['negative_y', [0, -1, 0]],
  ['positive_z', [0, 0, 1]],
  ['negative_z', [0, 0, -1]],
]

/** 把任意向量映射到最接近的六个朝向之一。 */
export function vectorToFacing(vector: Vector3): Direction {
  let best: Direction = 'positive_z'
  let score = -Infinity
  for (const [name, [x, y, z]] of AXES) {
    const value = vector.x * x + vector.y * y + vector.z * z
    if (value > score) {
      score = value
      best = name
    }
  }
  return best
}

export function facingVector(facing: Direction): Vector3 {
  const [x, y, z] = VECTORS[facing]
  return new Vector3(x, y, z)
}

/** 玩家在方块哪一侧，方块就朝向哪一侧。 */
export function facingTowardPlayer(position: { x: number; y: number; z: number }, player: Vector3): Direction {
  const delta = new Vector3(player.x - position.x, player.y - position.y, player.z - position.z)
  if (delta.lengthSq() === 0) return 'positive_z'
  return vectorToFacing(delta.normalize())
}

export type Swipe = 'left' | 'right' | 'up' | 'down'

/** 同一方向连续滑动会一直往同一方向转：左右绕竖直轴、上下绕相机右轴，每次固定 90°。 */
export function swipeFacing(facing: Direction, swipe: Swipe, cameraQuaternion: Quaternion): Direction {
  const right = new Vector3(1, 0, 0).applyQuaternion(cameraQuaternion)
  right.y = 0
  if (right.lengthSq() < 1e-6) right.set(1, 0, 0)
  right.normalize()
  const horizontal = swipe === 'left' || swipe === 'right'
  const current = facingVector(facing)
  if (horizontal) {
    const axis = new Vector3(0, 1, 0)
    const rotated = current.clone().applyAxisAngle(axis, swipe === 'left' ? -Math.PI / 2 : Math.PI / 2)
    if (Math.abs(rotated.dot(current)) > 0.999) {
      // 朝向正上或正下时竖直轴转不动，改为直接指向屏幕左右，后续滑动仍按同一方向继续。
      return vectorToFacing(swipe === 'left' ? right.clone().negate() : right.clone())
    }
    return vectorToFacing(rotated)
  }
  const rotated = current.clone().applyAxisAngle(right, swipe === 'up' ? -Math.PI / 2 : Math.PI / 2)
  if (Math.abs(rotated.dot(current)) > 0.999) {
    const forward = new Vector3(0, 0, -1).applyQuaternion(cameraQuaternion)
    return vectorToFacing(forward.clone().applyAxisAngle(right, swipe === 'up' ? -Math.PI / 2 : Math.PI / 2))
  }
  return vectorToFacing(rotated)
}

/** 连续滑动时的完整循环，便于检查每次是否都朝同一方向前进一步。 */
export function swipeSequence(facing: Direction, swipe: Swipe, cameraQuaternion: Quaternion, steps = 4): Direction[] {
  const result: Direction[] = []
  let current = facing
  for (let index = 0; index < steps; index += 1) {
    current = swipeFacing(current, swipe, cameraQuaternion)
    result.push(current)
  }
  return result
}

import { useMemo } from 'react'
import { Vector3 } from 'three'
import type { NormalizedStructure } from '../types'

export function ForwardIndicator({ shape }: { shape: NormalizedStructure }) {
  const direction = useMemo(() => new Vector3(0, 0, 1), [])
  const origin = useMemo(() => new Vector3(shape.width + 0.5, (shape.height - 1) / 2, -shape.depth - 1), [shape.width, shape.height, shape.depth])
  return (
    <group>
      <arrowHelper args={[direction, origin, shape.depth + 1, '#2279a2', 0.65, 0.4]} />
    </group>
  )
}

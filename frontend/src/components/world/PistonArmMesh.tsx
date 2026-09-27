import { useTexture } from '@react-three/drei'
import { useMemo } from 'react'
import { NearestFilter, SRGBColorSpace } from 'three'

import type { PistonArmState } from '@/types'

import { directionQuaternion } from './utils'

interface PistonArmMeshProps {
  arm: PistonArmState
  tick: number
}

export function PistonArmMesh({ arm, tick }: PistonArmMeshProps) {
  const [innerTexture, headTexture] = useTexture([
    '/textures/blocks/piston_inner.png',
    arm.sticky
      ? '/textures/blocks/piston_top_sticky.png'
      : '/textures/blocks/piston_top_normal.png',
  ])
  innerTexture.magFilter = NearestFilter
  innerTexture.minFilter = NearestFilter
  innerTexture.colorSpace = SRGBColorSpace
  headTexture.magFilter = NearestFilter
  headTexture.minFilter = NearestFilter
  headTexture.colorSpace = SRGBColorSpace

  const progress = useMemo(() => {
    if (arm.phase === 'extended' || arm.completes_at === null) return 1
    const duration = Math.max(1, arm.completes_at - arm.started_at)
    const raw = Math.min(1, Math.max(0, (tick - arm.started_at) / duration))
    return arm.phase === 'retracting' ? 1 - raw : raw
  }, [arm, tick])
  const quaternion = useMemo(() => directionQuaternion(arm.facing), [arm.facing])
  const headOffset = -(1 - progress) * 0.45
  const rodLength = 0.22 + progress * 0.62

  return (
    <group
      position={[arm.position.x, arm.position.y, arm.position.z]}
      quaternion={quaternion}
    >
      <mesh position={[0, 0, headOffset]} castShadow>
        <boxGeometry args={[0.94, 0.94, 0.22]} />
        <meshStandardMaterial map={headTexture} roughness={0.84} />
      </mesh>
      <mesh position={[0, 0, -0.48]} castShadow>
        <boxGeometry args={[0.34, 0.34, rodLength]} />
        <meshStandardMaterial map={innerTexture} roughness={0.84} />
      </mesh>
    </group>
  )
}

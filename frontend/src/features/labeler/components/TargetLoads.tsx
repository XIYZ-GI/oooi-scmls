import { useLayoutEffect, useMemo, useRef } from 'react'
import { InstancedMesh, Matrix4 } from 'three'
import { BoxOutline } from '@/components/world'
import { TARGET_LOAD_BLOCKS } from '../constants'
import type { LabelSample } from '../types'
import { FAILED_TARGET_COLOR, targetFailed, targetResult } from '../utils/targetStatus'

export function TargetLoads({ sample, showFullLoad }: { sample: LabelSample; showFullLoad: boolean }) {
  const mesh = useRef<InstancedMesh>(null)
  const positions = useMemo(() => sample.targets.flatMap((point) =>
    Array.from({ length: showFullLoad ? TARGET_LOAD_BLOCKS : 1 }, (_, offset) => [point.x, point.y, (point.z ?? 0) + offset] as const),
  ), [sample.targets, showFullLoad])
  useLayoutEffect(() => {
    if (!mesh.current) return
    const matrix = new Matrix4()
    positions.forEach(([x, y, z], index) => mesh.current!.setMatrixAt(index, matrix.makeTranslation(x, y, z)))
    mesh.current.instanceMatrix.needsUpdate = true
    mesh.current.computeBoundingSphere()
  }, [positions])
  return <group>
    {!!positions.length && <instancedMesh ref={mesh} args={[undefined, undefined, positions.length]} raycast={() => null}>
      <boxGeometry args={[0.92, 0.92, 0.92]} />
      <meshStandardMaterial color="#c9d6dd" transparent opacity={0.55} roughness={0.8} depthWrite={false} />
    </instancedMesh>}
    {sample.targets.map((target) => {
      const failed = targetFailed(targetResult(sample.timing, target))
      return <group key={`${target.x},${target.y}`} position={[target.x, target.y, target.z ?? 0]}>
        <BoxOutline size={0.96} color={failed ? FAILED_TARGET_COLOR : '#2279a2'} />
        {failed && <mesh raycast={() => null}><boxGeometry args={[0.94, 0.94, 0.94]} /><meshBasicMaterial color={FAILED_TARGET_COLOR} transparent opacity={0.65} depthWrite={false} /></mesh>}
      </group>
    })}
  </group>
}

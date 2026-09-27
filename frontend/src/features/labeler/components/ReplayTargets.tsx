import { BoxOutline } from '@/components/world'
import { motionPosition } from '@/components/world/utils'
import type { SimulationSnapshot } from '@/types'
import type { LabelReplayInfo } from '../hooks/useLabelReplay'
import { FAILED_TARGET_COLOR, targetFailed } from '../utils/targetStatus'

export function ReplayTargets({ info, snapshot }: { info: LabelReplayInfo; snapshot: SimulationSnapshot }) {
  const blocks = new Map(snapshot.blocks.map(block => [block.id, block]))
  return <group>{info.targets.map(target => {
    const head = blocks.get(target.blockIds[0])
    const position = head ? motionPosition(head, snapshot.tick, snapshot.motions) : [target.x, target.y, target.z] as [number, number, number]
    const failed = targetFailed(target)
    return <group key={`${target.x},${target.y}`} position={position}>
      <BoxOutline size={1.04} color={failed ? FAILED_TARGET_COLOR : '#2279a2'} />
      {failed && <mesh raycast={() => null}>
        <boxGeometry args={[1.012, 1.012, 1.012]} />
        <meshBasicMaterial color={FAILED_TARGET_COLOR} transparent opacity={0.55} depthWrite={false} />
      </mesh>}
    </group>
  })}</group>
}

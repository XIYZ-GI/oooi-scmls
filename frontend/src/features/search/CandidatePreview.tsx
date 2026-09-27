import { useMemo, useState } from 'react'
import { WorldCanvas } from '@/components/world'
import type { SimulationSnapshot } from '@/types'
import { BUTTON_CLASS } from '../labeler/constants'
import type { CandidateDetail } from './types'

const noop = () => undefined

export function CandidatePreview({ detail }: { detail: CandidateDetail }) {
  const [original, setOriginal] = useState(false)
  const [loads, setLoads] = useState(false)
  const blocks = original ? detail.seed.request.blocks : detail.candidate.blocks
  const push = original ? detail.seed.request.push_point : detail.candidate.push
  const snapshot = useMemo<SimulationSnapshot>(() => ({
    tick: 0, motions: [], arms: [], events: [],
    blocks: [...blocks, ...(loads ? detail.seed.request.targets.flatMap(point =>
      Array.from({ length: 10 }, (_, offset) => ({ position: { ...point, z: point.z + offset }, block: { kind: 'iron_block' as const, facing: 'positive_z' as const } }))) : [])]
      .map((b, index) => ({ ...b.block, position: b.position, id: index + 1, powered: false, strongly_powered: false, piston_phase: null, observer_phase: null })),
  }), [blocks, loads, detail.seed.request.targets])
  const view = useMemo(() => ({
    target: [(detail.seed.width - 1) / 2, (detail.seed.height - 1) / 2, -detail.seed.depth / 2] as [number, number, number],
    distance: Math.max(detail.seed.width, detail.seed.height, detail.seed.depth, loads ? 14 : 5) * 1.5,
  }), [detail.seed.width, detail.seed.height, detail.seed.depth, loads])
  return <div className="flex h-full min-h-80 flex-col bg-bench">
    <div className="min-h-72 flex-1">
      <WorldCanvas snapshot={snapshot} selectedPosition={null} disabled view={view} showGround={false}
        onSelect={noop} onBlockAction={noop} onGroundAction={noop} onErase={noop}>
        <mesh position={[push.x, push.y, push.z - 1]}>
          <boxGeometry args={[0.8, 0.8, 0.8]} /><meshBasicMaterial color="#c84c4c" wireframe />
        </mesh>
      </WorldCanvas>
    </div>
    <div className="flex h-11 shrink-0 items-center justify-center gap-2 border-t border-ink/10 bg-white">
      <button className={BUTTON_CLASS} onClick={() => setOriginal(v => !v)}>{original ? '显示候选' : '对照原样本'}</button>
      <button className={BUTTON_CLASS} onClick={() => setLoads(v => !v)}>{loads ? '隐藏负载' : '显示十块负载'}</button>
    </div>
  </div>
}

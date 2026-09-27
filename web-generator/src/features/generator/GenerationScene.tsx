import { useMemo, useRef, useState } from 'react'
import { WorldCanvas, BoxOutline } from '@/components/world'
import { motionPosition } from '@/components/world/utils'
import type { SimulationSnapshot, WorldBlockInput } from '@/types'
import type { Proposal, Task } from './types'
import { TargetGrid } from './TargetGrid'
import { SurfaceNumber } from './SurfaceNumber'
import { groupColor } from './constants'

const noop = () => undefined
const empty: SimulationSnapshot = { tick: 0, blocks: [], arms: [], motions: [], events: [] }

export function GenerationScene({ task, loadTask, editing, proposal, loads, frame, initial, onMark, onResize, onResizeCommit, resetKey }: {
  task: Task; loadTask?: Task; editing: boolean; proposal?: Proposal; loads: boolean
  frame?: SimulationSnapshot; initial?: SimulationSnapshot
  onMark: (x: number, y: number) => void; resetKey: number
  onResize?: (changes: { width?: number; height?: number }, anchor: 'start' | 'end') => void
  onResizeCommit?: () => void
}) {
  const [resizing, setResizing] = useState(false)
  // 绘制原点偏移：从左/下边加列时把整个场景往那个方向挪，视觉上就是网格朝拖动方向生长。
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const resize = (changes: { width?: number; height?: number }, anchor: 'start' | 'end') => {
    if (anchor === 'start') {
      const dx = changes.width !== undefined ? changes.width - task.width : 0
      const dy = changes.height !== undefined ? changes.height - task.height : 0
      if (dx || dy) setOffset(current => ({ x: current.x + dx, y: current.y + dy }))
    }
    onResize?.(changes, anchor)
  }
  const snapshot = useMemo<SimulationSnapshot>(() => {
    if (editing || !proposal) return empty
    if (frame) return frame
    const blocks: WorldBlockInput[] = [...proposal.blocks]
    // 负载按生成结构的本列前端摆放（loadTask 由服务端算好），需求本身仍按 task 显示目标。
    blocks.push(...(loadTask ?? task).targets.flatMap(t => Array.from({ length: loads ? 10 : 1 }, (_, i) => ({
      position: { x: t.x, y: t.y, z: t.z+i }, block: { kind: 'iron_block' as const, facing: 'positive_z' as const },
    }))))
    blocks.push({ position: { ...proposal.push, z: proposal.push.z-1 }, block: { kind: 'piston', facing: 'positive_z' } })
    return { ...empty, blocks: blocks.map((b, i) => ({ ...b.block, position: b.position, id: i+1,
      powered: false, strongly_powered: false, piston_phase: null, observer_phase: null })) }
  }, [editing, proposal, frame, loads, task, loadTask])
  const framing = useMemo(() => {
    // 编辑态网格按偏移绘制，镜头跟着偏移；生成结构与标记都在设计坐标里，不偏移。
    const shift = editing ? offset : { x: 0, y: 0 }
    const center: [number, number, number] = [(task.width-1)/2 - shift.x, (task.height-1)/2 - shift.y, editing ? 0 : (loads || frame ? 9-task.depth : -task.depth-1)/2]
    const distance = Math.max(task.width, task.height, editing ? 2 : loads || frame ? task.depth+11 : task.depth+2)*1.6
    return { target: center, distance, position: editing ? [center[0], center[1]+.4, distance] as [number, number, number] : undefined }
    // 回放过程中维持相机位置，只有开始/退出回放时调整构图。
  }, [task.width, task.height, task.depth, editing, loads, !!frame, offset])
  // 只在切换编辑/回放模式或手动重置视角时重新构图；改网格尺寸（含拖边缘）不移动相机。
  const viewKey = `${editing ? 1 : 0}|${loads ? 1 : 0}|${frame ? 1 : 0}|${resetKey}`
  const applied = useRef(framing)
  const appliedKey = useRef(viewKey)
  if (appliedKey.current !== viewKey) {
    appliedKey.current = viewKey
    applied.current = framing
  }
  const appliedView = applied.current
  return <WorldCanvas key={resetKey} snapshot={snapshot} selectedPosition={null} disabled={!editing} view={appliedView} showGround={false}
    lockControls={resizing}
    onSelect={noop} onBlockAction={noop} onGroundAction={noop} onErase={noop}>
    {editing ? <TargetGrid task={task} offset={offset} onMark={onMark} onResize={resize}
        onDragChange={active => { setResizing(active); if (!active) onResizeCommit?.() }} /> : (loadTask ?? task).targets.map(t => {
      const source = initial?.blocks.find(b => b.position.x === t.x && b.position.y === t.y && b.position.z === t.z)
      const moving = source && frame ? frame.blocks.find(b => b.id === source.id) : undefined
      const position: [number, number, number] = moving && frame ? motionPosition(moving, frame.tick, frame.motions) : [t.x, t.y, t.z]
      return <group key={`${t.x},${t.y}`} position={position}>
        <BoxOutline color={groupColor(t.order)} size={1.015} />
        <SurfaceNumber order={t.order} offset={.509} size={.48} />
      </group>
    })}
    {!editing && proposal && !frame && <group position={[proposal.push.x, proposal.push.y, proposal.push.z]}>
      <BoxOutline color="#bf7764" size={1.04} />
    </group>}
  </WorldCanvas>
}

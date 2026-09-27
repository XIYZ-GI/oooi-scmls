import { useMemo } from 'react'
import { DoubleSide } from 'three'
import type { Task } from './types'
import { groupColor } from './constants'
import { SurfaceNumber } from './SurfaceNumber'
import { useGridResize } from './useGridResize'

/** 边缘拖拽手柄；必须渲染在 Canvas 内，才能使用 R3F 的相机与指针事件。 */
function EdgeHandles({ task, offset, onResize, onDragChange }: {
  task: Task
  offset: { x: number; y: number }
  onResize: (changes: { width?: number; height?: number }, anchor: 'start' | 'end') => void
  onDragChange?: (active: boolean) => void
}) {
  const begin = useGridResize({ enabled: true, onResize, onDragChange })
  // 判定面放在相机一侧并完全透明，四周各留半格；网格内部仍然用于标注目标点。
  return <mesh position={[(task.width - 1) / 2, (task.height - 1) / 2, 4]}
    onPointerDown={begin({ width: task.width, height: task.height, offset })}>
    <planeGeometry args={[task.width + 1, task.height + 1]} />
    <meshBasicMaterial transparent opacity={0} depthWrite={false} />
  </mesh>
}

export function TargetGrid({ task, offset = { x: 0, y: 0 }, onMark, onResize, onDragChange }: {
  task: Task; onMark: (x: number, y: number) => void
  offset?: { x: number; y: number }
  onResize?: (changes: { width?: number; height?: number }, anchor: 'start' | 'end') => void
  onDragChange?: (active: boolean) => void
}) {
  const tiles = useMemo(() => Array.from({ length: task.width*task.height }, (_, i) =>
    ({ x: i % task.width, y: Math.floor(i/task.width) })), [task.width, task.height])
  // 只有编辑态的网格按偏移绘制：从左/下边加列时，网格看起来是朝那个方向长的。
  return <group position={[-offset.x, -offset.y, 0]}>{tiles.map(({ x, y }) => {
    const target = task.targets.find(t => t.x === x && t.y === y)
    return <group key={`${x},${y}`} position={[x, y, 0]}>
      <mesh onClick={event => { event.stopPropagation(); if (event.button === 0 && event.delta < 5) onMark(x, y) }}>
        <boxGeometry args={[.95, .95, .1]} />
        <meshStandardMaterial color={target ? groupColor(target.order) : '#eef6f8'} side={DoubleSide} roughness={.85} />
      </mesh>
      {target && <SurfaceNumber order={target.order} />}
    </group>
  })}
    {onResize && <EdgeHandles task={task} offset={offset} onResize={onResize} onDragChange={onDragChange} />}
  </group>
}

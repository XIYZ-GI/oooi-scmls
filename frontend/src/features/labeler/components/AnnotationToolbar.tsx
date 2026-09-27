import { Boxes, Crosshair, Eraser, Layers3, RotateCcw, Scan } from 'lucide-react'
import type { ReactNode, RefObject } from 'react'
import type { Camera } from 'three'
import type { Direction } from '@/types'
import { cn } from '@/lib'
import { COMPACT_TOOL_CLASS } from '../constants'
import type { MarkTool } from '../types'
import { CameraDirectionControl } from './CameraDirectionControl'

export function AnnotationToolbar({ forward, onForward, cameraRef, tool, onTool, showFullLoad, onLoadToggle, slice, depth, onSlice, onReset, mobileActions, runControl }: {
  forward: Direction
  onForward: (direction: Direction) => Promise<void>
  cameraRef: RefObject<Camera | null>
  tool: MarkTool
  onTool: (tool: MarkTool) => void
  showFullLoad: boolean
  onLoadToggle: () => void
  slice: number
  depth: number
  onSlice: (slice: number) => void
  onReset: () => void
  mobileActions: ReactNode
  runControl: ReactNode
}) {
  return <div className="flex h-11 min-w-0 shrink-0 flex-nowrap items-center justify-center gap-0.5 overflow-hidden border-t border-ink/15 bg-frost px-1" aria-label="三维标注工具栏">
    {runControl}
    <CameraDirectionControl forward={forward} onChange={onForward} cameraRef={cameraRef} />
    {([
      { value: 'target', label: '目标点', icon: Scan },
      { value: 'push', label: '推动点', icon: Crosshair },
      { value: 'erase', label: '擦除', icon: Eraser },
    ] as const).map(({ value, label, icon: Icon }) => <button
      key={value} type="button" aria-label={label} aria-pressed={tool === value}
      className={cn(COMPACT_TOOL_CLASS, tool === value && 'border-sky-500 bg-sky-100 text-sky-900')}
      onClick={() => onTool(value)}
    ><Icon size={16} /></button>)}
    <button type="button" className={cn(COMPACT_TOOL_CLASS, showFullLoad && 'border-sky-500 bg-sky-100')} aria-label="显示整列十块负载" aria-pressed={showFullLoad} onClick={onLoadToggle}><Boxes size={16} /></button>
    <button type="button" className={COMPACT_TOOL_CLASS} aria-label={`切换显示层数，当前 ${slice + depth + 2} 层，共 ${depth} 层`} disabled={depth <= 1} onClick={() => onSlice(slice <= -depth - 1 ? -2 : slice - 1)}><Layers3 size={16} /></button>
    <button type="button" className={COMPACT_TOOL_CLASS} aria-label="重置标注视角" onClick={onReset}><RotateCcw size={16} /></button>
    <div className="contents lg:hidden">{mobileActions}</div>
  </div>
}

import { useAutoAnimate } from '@formkit/auto-animate/react'
import { ArrowDown, ArrowUp, LocateFixed, RotateCcw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { cn } from '@/lib'
import { BUTTON_CLASS, MAX_TARGET_Z, TARGET_LOAD_BLOCKS } from '../constants'
import type { LabelSample, NormalizedStructure, TargetPoint } from '../types'
import { columnFront, defaultTargetDepth } from '../utils'
import { targetFailed, targetResult } from '../utils/targetStatus'

export function TargetList({ sample, shape, onUpdate, onFocus }: {
  sample: LabelSample
  shape: NormalizedStructure
  onUpdate: (patch: Partial<LabelSample>) => void
  onFocus: (point: TargetPoint) => void
}) {
  const [list] = useAutoAnimate()
  const [onlyFailed, setOnlyFailed] = useState(false)
  const failures = sample.targets.filter(point => targetFailed(targetResult(sample.timing, point)))
  const change = (point: TargetPoint, z: number) => onUpdate({
    completed: false,
    targets: sample.targets.map((item) => item.x === point.x && item.y === point.y ? { ...item, z } : item),
  })
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold">目标点 · {sample.targets.length}</h2>
      {sample.timing && <label className="flex items-center gap-2 text-xs text-purple-800"><input type="checkbox" checked={onlyFailed} onChange={event => setOnlyFailed(event.target.checked)} />仅失败目标 · {failures.length}/{sample.targets.length}</label>}
      {!!sample.targets.length && <button className={`${BUTTON_CLASS} w-full text-xs`} onClick={() => {
        const previous = sample.targets
        onUpdate({ targets: sample.targets.map((point) => ({ ...point, z: defaultTargetDepth(shape, point) })), completed: false })
        toast.info('各列负载已放到对应方块前方，留一格空气', { duration: 15000, action: { label: '撤销', onClick: () => onUpdate({ targets: previous, completed: false }) } })
      }}><RotateCcw size={14} />全部按各列前端摆放</button>}
      <div ref={list} className="space-y-3">
        {!sample.targets.length && <p className="py-2 text-xs text-ink/50">选择“目标点”，点击截面或三维方块添加。</p>}
        {[...(onlyFailed && sample.timing ? failures : sample.targets)].sort((a, b) => a.y - b.y || a.x - b.x).map((point) => {
          const z = point.z ?? 0
          const front = columnFront(shape, point)
          const gap = z - front - 1
          const result = targetResult(sample.timing, point)
          const failed = targetFailed(result)
          return <div key={`${point.x},${point.y}`} className={cn('space-y-2 border-b border-ink/10 pb-3', failed && 'border-purple-300 bg-purple-50/70')} data-failed={failed}>
            <div className="flex items-center gap-2 text-sm">
              <span className={cn('font-mono text-xs', failed && 'text-purple-800')}>({point.x}, {point.y}, {z})</span>
              <span className={cn('min-w-0 flex-1 text-xs text-ink/60', failed && 'text-purple-800')}>{failed ? `未通过 · ${result?.movedBlocks ?? 0}/${TARGET_LOAD_BLOCKS} 块` : result?.tick != null ? `第 ${result.tick} 刻${result.order ? ` · 第 ${result.order} 组` : ''}` : '待计算'}</span>
              <button className="flex h-8 w-7 shrink-0 items-center justify-center" aria-label={`定位目标 ${point.x},${point.y}`} title="定位目标" onClick={() => onFocus(point)}><LocateFixed size={15} /></button>
              <button className={BUTTON_CLASS} aria-label={`删除目标 ${point.x},${point.y}`} onClick={() => onUpdate({ completed: false, targets: sample.targets.filter((item) => item.x !== point.x || item.y !== point.y) })}><Trash2 size={14} /></button>
            </div>
            {result?.error && <p className="text-xs text-purple-800">{result.error}</p>}
            <div className="flex items-center gap-2">
              <button className={`${BUTTON_CLASS} px-2 text-xs`} aria-label={`目标 ${point.x},${point.y} 靠近一格`} disabled={z <= front + 1} onClick={() => change(point, z - 1)}><ArrowDown size={14} />靠近</button>
              <span className="flex-1 text-center text-xs text-ink/60">{gap === 0 ? '紧贴前端' : `间隔 ${gap} 格空气`}</span>
              <button className={`${BUTTON_CLASS} px-2 text-xs`} aria-label={`目标 ${point.x},${point.y} 远离一格`} disabled={z >= MAX_TARGET_Z} onClick={() => change(point, z + 1)}><ArrowUp size={14} />远离</button>
            </div>
          </div>
        })}
        {onlyFailed && sample.timing && !failures.length && <p className="py-2 text-xs text-ink/60">没有失败目标</p>}
      </div>
    </section>
  )
}

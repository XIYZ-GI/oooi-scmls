import { Download, Eraser, Plus, Trash2, Undo2 } from 'lucide-react'
import { useAutoAnimate } from '@formkit/auto-animate/react'
import { cn } from '@/lib'
import { ICON_BUTTON, groupColor } from './constants'
import { DEPTH_LIMIT, GRID_LIMIT, resizeTask } from './taskEdit'
import { NumberField } from './NumberField'
import type { Task } from './types'

/** 画布上方的常驻工具条：网格尺寸、时序组与目标点操作不必展开侧栏即可修改。 */
export function TaskToolbar({ task, groups, active, disabled, erase, canUndo, exportDisabled, onTask, onGroups, onActive, onErase, onUndo, onClear, onExport }: {
  task: Task; groups: number; active: number; disabled: boolean; erase: boolean; canUndo: boolean
  exportDisabled: boolean
  onTask: (task: Task) => void; onGroups: (groups: number) => void; onActive: (group: number) => void
  onErase: (value: boolean) => void; onUndo: () => void; onClear: () => void; onExport: () => void
}) {
  const [groupList] = useAutoAnimate()
  const size = (label: string, key: 'width' | 'height' | 'depth', limit: { min: number; max: number }, aria = `网格${label}`) =>
    <label className="flex shrink-0 items-center gap-1 text-xs text-ink/60">{label}
      <NumberField aria={aria} value={task[key]} min={limit.min} max={limit.max} disabled={disabled}
        className="w-11 sm:w-14" onCommit={value => { const next = resizeTask(task, { [key]: value }); if (next) onTask(next) }} />
    </label>
  return <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1.5 border-b border-ink/15 bg-frost px-2 py-1.5">
    {/* 尺寸与擦除、撤回、删除、导出始终同一行，手机端也不会被拆开。 */}
    <div className="flex shrink-0 items-center gap-1.5">
      {size('宽', 'width', GRID_LIMIT)}{size('高', 'height', GRID_LIMIT)}{size('厚', 'depth', DEPTH_LIMIT, '最大厚度')}
      <button className={cn(ICON_BUTTON, 'h-7 w-7 sm:h-8 sm:w-8', erase && 'border-sky-500 bg-sky-50')} aria-label="擦除目标点" title="擦除目标点" onClick={() => onErase(!erase)}><Eraser size={14} /></button>
      <button className={cn(ICON_BUTTON, 'h-7 w-7 sm:h-8 sm:w-8')} aria-label="撤回上一步" title="撤回上一步" disabled={!canUndo} onClick={onUndo}><Undo2 size={14} /></button>
      <button className={cn(ICON_BUTTON, 'h-7 w-7 sm:h-8 sm:w-8')} aria-label="删除所有点" title="删除所有点" disabled={!task.targets.length} onClick={onClear}><Trash2 size={14} /></button>
      <button className={cn(ICON_BUTTON, 'h-7 w-7 sm:h-8 sm:w-8')} aria-label="导出结构" title="导出 .mcstructure 结构" disabled={exportDisabled} onClick={onExport}><Download size={14} /></button>
    </div>
    <span className="h-5 w-px shrink-0 bg-ink/10" />
    {/* 手机端时序组另起一行，桌面端接在同一行。 */}
    <div className="flex w-full min-w-0 items-center gap-1 sm:w-auto">
    <span className="shrink-0 text-xs text-ink/55">时序组</span>
    {/* 组多时横向滚动，加号固定在原位，不会被挤出去。 */}
    <div className="min-w-0 flex-1 overflow-x-auto [scrollbar-width:none] sm:flex-none [&::-webkit-scrollbar]:hidden">
    <div ref={groupList} className="flex w-max items-center gap-1">
      {Array.from({ length: groups }, (_, i) => i+1).map(order =>
        <div key={order} className={cn('flex shrink-0 items-center rounded-md border bg-white', active === order && !erase ? 'border-sky-500' : 'border-ink/10')}>
          <button className="flex h-7 items-center gap-1 px-1.5 text-xs" onClick={() => { onActive(order); onErase(false) }}>
            <span className="flex h-4 w-4 items-center justify-center rounded text-[10px] text-ink" style={{ background: groupColor(order) }}>{order}</span>
          </button>
          {groups > 1 && <button className="flex h-6 w-6 items-center justify-center text-ink/40 hover:text-red-700" aria-label={`删除第${order}组及目标`} title={`删除第${order}组及目标`}
            onClick={() => { onTask({ ...task, targets: task.targets.filter(t => t.order !== order).map(t => ({ ...t, order: t.order > order ? t.order-1 : t.order })) }); onGroups(groups-1); onActive(Math.min(active, groups-1)) }}><Trash2 size={11} /></button>}
        </div>)}
    </div>
    </div>
    {/* 加号放在动画容器外，避免被 auto-animate 的补间带着位移。 */}
    <button className={cn(ICON_BUTTON, 'h-7 w-7 shrink-0')} aria-label="添加时序组" title="添加时序组" disabled={groups >= 32}
      onClick={() => { onGroups(groups+1); onActive(groups+1); onErase(false) }}><Plus size={13} /></button>
    </div>
  </div>
}

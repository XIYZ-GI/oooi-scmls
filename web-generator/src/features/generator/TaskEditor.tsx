import { MAX_CANDIDATES } from './constants'
import { NumberField } from './NumberField'
import type { Task } from './types'

/** 侧栏剩余设置：网格尺寸、时序组与目标点操作已移到画布上方常驻工具条。
 *
 * ``judgeOnly`` 表示当前模型不把每轮时限与连续轮数读进网络。这两项只用于判定，
 * 因此选中这类版本时不再显示输入框；需求里仍保留服务器给的默认值，判定照常执行。
 */
export function TaskEditor({ task, disabled, candidateCount, onCandidateCount, onTask, judgeOnly = false }: {
  task: Task; disabled: boolean
  candidateCount: number; onCandidateCount: (count: number) => void
  onTask: (task: Task) => void
  judgeOnly?: boolean
}) {
  const number = (label: string, key: 'max_ticks' | 'rounds', min: number, max: number) =>
    <label className="space-y-1 text-xs text-ink/60">{label}
      <NumberField aria={label} value={task[key]} min={min} max={max} disabled={disabled}
        onCommit={value => onTask({ ...task, [key]: value })} /></label>
  return <fieldset disabled={disabled} className="space-y-4 disabled:opacity-50">
    {!judgeOnly && <div className="grid grid-cols-2 gap-2">
      {number('每轮时限 / 刻', 'max_ticks', 8, 200)}{number('连续轮数', 'rounds', 2, 10)}
    </div>}
    <label className="flex items-center justify-between gap-2 text-xs text-ink/60">候选数量
      <NumberField aria="候选数量" className="w-24" value={candidateCount} min={1} max={MAX_CANDIDATES}
        onCommit={onCandidateCount} />
    </label>
  </fieldset>
}

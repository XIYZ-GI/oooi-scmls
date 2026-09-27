import { LoaderCircle, RefreshCw } from 'lucide-react'
import type { useAutomaticTiming } from '../hooks/useAutomaticTiming'
import type { LabelSample } from '../types'
import { BUTTON_CLASS, FIELD_CLASS, TARGET_LOAD_BLOCKS } from '../constants'

export function TimingPanel({
  sample,
  calculation,
}: {
  sample: LabelSample
  calculation: ReturnType<typeof useAutomaticTiming>
}) {
  const busy =
    calculation.phase === 'waiting' || calculation.phase === 'running'
  return (
    <section className="space-y-2 rounded-md border border-sky-200 bg-sky-50/70 p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">模拟器自动时序</h2>
        <label className="flex min-h-10 items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={calculation.enabled}
            onChange={(event) => calculation.setEnabled(event.target.checked)}
          />
          自动计算
        </label>
      </div>
      <p className="text-xs leading-5 text-ink/60">
        所有目标同时各放一列 {TARGET_LOAD_BLOCKS} 个铁块，按各自设定的位置摆放。每列全部前进一格才算通过，完成刻相同的目标归为同组。
      </p>
      {calculation.blocked ? (
        <p className="text-xs text-amber-800">{calculation.blocked}</p>
      ) : calculation.message ? (
        <p className="flex items-center gap-2 text-xs" role="status">
          {busy && <LoaderCircle size={14} className="shrink-0 animate-spin" />}
          {calculation.message}
        </p>
      ) : sample.timing ? (
        <p className="text-xs leading-5">
          {sample.timing.status === 'success'
            ? `已通过：${sample.timing.targets.length} 个目标均推动 ${TARGET_LOAD_BLOCKS} 块负载，最后完成于第 ${sample.timing.simulatedTicks} 游戏刻`
            : sample.timing.reason}
        </p>
      ) : (
        <p className="text-xs text-ink/50">
          标好推动点和至少一个目标点后自动开始。
        </p>
      )}
      <button
        className={`${BUTTON_CLASS} w-full`}
        disabled={
          busy ||
          !calculation.enabled ||
          !!calculation.blocked ||
          !sample.pushPoint ||
          !sample.targets.length
        }
        onClick={calculation.retry}
      >
        <RefreshCw size={14} />
        重新计算
      </button>
      <details className="text-xs text-ink/60">
        <summary className="cursor-pointer py-1">计算设置与说明</summary>
        <label className="mt-2 flex items-center gap-2">
          最多模拟游戏刻
          <input
            className={`${FIELD_CLASS} w-24`}
            aria-label="最多模拟游戏刻"
            type="number"
            min={8}
            max={2000}
            value={calculation.maxTicks}
            onChange={(event) =>
              calculation.setMaxTicks(
                Math.max(
                  8,
                  Math.min(2000, Math.trunc(Number(event.target.value)) || 200),
                ),
              )
            }
          />
        </label>
        <p className="mt-2 leading-5">
          以触发外部活塞为第 0 刻，供电持续 4
          刻；固定要求每个目标推动 {TARGET_LOAD_BLOCKS} 块，不能降低数量。计算截止于全部负载完成或达到上限，提取单次推动时序，不判定成品能否连续运行。
        </p>
      </details>
    </section>
  )
}

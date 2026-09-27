import { Square } from 'lucide-react'
import { OverlayScrollbarsComponent } from 'overlayscrollbars-react'
import { cn } from '@/lib'
import { BUTTON, STATUS, busyJob } from './constants'
import type { Job } from './types'

export function ResultPanel({ job, candidate, busy, onCandidate, onCancel }: {
  job: Job; candidate: number; busy: boolean; onCandidate: (index: number) => void; onCancel: () => void
}) {
  const result = job.result
  const proposal = result?.proposals[candidate]
  const evaluation = result?.evaluations[candidate]
  const accepted = result?.evaluations.filter(value => value.accepted).length ?? 0
  const partial = result?.evaluations.filter(value => !value.accepted && value.partial).length ?? 0
  const zs = proposal?.blocks.map(b => b.position.z) ?? []
  return <section className="space-y-3 border-y border-ink/10 py-4">
    <div className="flex items-center justify-between gap-2"><h2 className="min-w-0 truncate text-xs font-medium">{job.name}</h2>
      <span className={cn('shrink-0 text-xs', job.status === 'success' ? 'text-emerald-700' : result?.partial ? 'text-amber-600' : 'text-ink/55')}>{STATUS[job.status]}</span></div>
    <p className="text-xs text-ink/60" role="status">{job.message}</p>
    {busyJob(job.status) && <>
      <div className="h-1.5 overflow-hidden rounded bg-sky-100" role="progressbar" aria-valuenow={job.progress} aria-valuemin={0} aria-valuemax={100} aria-label="生成进度"><div className="h-full bg-sky-500 transition-all" style={{ width: `${job.progress}%` }} /></div>
      <button className={BUTTON} disabled={busy} onClick={onCancel}><Square size={13} />取消生成</button>
    </>}
    {result && <>
      {result.model_name && <p className="text-xs text-ink/55">{result.model_name}</p>}
      <p className="text-xs text-ink/55">{result.proposals.length} 个候选 · {accepted} 个通过{partial ? ` · ${partial} 个半通过` : ''}</p>
      <OverlayScrollbarsComponent className="max-h-40 overflow-auto" options={{ overflow: { x: 'hidden' }, scrollbars: { autoHide: 'leave' } }}>
      <div className="grid grid-cols-4 gap-1.5">{result.proposals.map((_, i) => <button key={i}
        className={cn(BUTTON, 'px-1', candidate === i && 'border-sky-500 bg-sky-50',
          result.evaluations[i].accepted ? 'text-emerald-700'
            : result.evaluations[i].partial ? 'text-amber-600' : 'text-red-700/70')}
        onClick={() => onCandidate(i)} aria-pressed={candidate === i}>候选 {i+1}</button>)}</div>
      </OverlayScrollbarsComponent>
      <p className={cn('text-xs', evaluation?.accepted ? 'text-emerald-700' : evaluation?.partial ? 'text-amber-700' : 'text-red-700')}>
        {evaluation?.accepted ? `${job.task.rounds} 轮全部通过`
          : evaluation?.partial ? `半通过：负载可推动，${evaluation.partial_reason || evaluation.reason}`
          : evaluation?.reason || '未完整通过'}
      </p>
      {evaluation?.foundation && <p className="text-xs text-ink/60">
        本体搬运：{evaluation.foundation.translation ? '通过' : '未通过'} · 活塞激活：{evaluation.foundation.activation ? '通过' : '未通过'}
      </p>}
      <p className="text-xs text-ink/55">{zs.length} 方块 · 实际厚度 {zs.length ? Math.max(...zs)-Math.min(...zs)+1 : 0} 格</p>
      {!!evaluation?.rounds.length && <div className="text-xs text-ink/60">首轮各组完成刻：{[...new Set(evaluation.rounds[0].ticks)].sort((a, b) => a-b).map((tick, i) => `${i+1}组 ${tick}刻`).join('，')}</div>}
    </>}
  </section>
}

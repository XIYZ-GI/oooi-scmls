import { useState } from 'react'
import { Play, Save } from 'lucide-react'
import { BUTTON_CLASS, FIELD_CLASS } from '../labeler/constants'
import type { SearchJob } from './types'

export function JobSettings({ job, busy, onSubmit }: {
  job?: SearchJob; busy: boolean; onSubmit: (body: { name: string; per_seed: number; rounds?: number }) => Promise<void>
}) {
  const [name, setName] = useState(job?.name ?? `移动线搜索 ${new Date().toLocaleDateString('zh-CN')}`)
  const [budget, setBudget] = useState(job?.config.per_seed ?? 32)
  const [rounds, setRounds] = useState(job?.config.rounds ?? 3)
  const running = job?.state === 'running' || job?.state === 'queued'
  return <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
    event.preventDefault()
    void onSubmit({ name: name.trim(), per_seed: budget, ...(job ? {} : { rounds }) })
  }}>
    <label className="min-w-32 flex-1 text-xs">任务名称
      <input className={FIELD_CLASS} required maxLength={100} value={name} onChange={event => setName(event.target.value)} />
    </label>
    <label className="w-24 text-xs">每样本候选数
      <input className={FIELD_CLASS} type="number" min={1} max={10000} required disabled={running} value={budget} onChange={event => setBudget(Number(event.target.value))} />
    </label>
    {!job && <label className="w-24 text-xs">连续运行轮数
      <input className={FIELD_CLASS} type="number" min={2} max={20} required value={rounds} onChange={event => setRounds(Number(event.target.value))} />
    </label>}
    <button className={BUTTON_CLASS} disabled={busy || !name.trim()} type="submit">
      {job ? <Save size={16} /> : <Play size={16} />}{busy ? '处理中…' : job ? '保存设置' : '开始搜索'}
    </button>
  </form>
}

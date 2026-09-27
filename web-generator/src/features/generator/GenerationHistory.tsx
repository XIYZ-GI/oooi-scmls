import { useState } from 'react'
import { useAutoAnimate } from '@formkit/auto-animate/react'
import { Pencil, Trash2, Check, X } from 'lucide-react'
import { cn } from '@/lib'
import { DEFAULT_CANDIDATES, FIELD, ICON_BUTTON, STATUS } from './constants'
import type { Job } from './types'

export function GenerationHistory({ jobs, selected, busy, onSelect, onRemove, onRename }: {
  jobs: Job[]; selected?: string; busy: boolean; onSelect: (id: string) => void
  onRemove: (id: string) => void; onRename: (id: string, name: string) => Promise<void>
}) {
  const [filter, setFilter] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [list] = useAutoAnimate()
  const visible = jobs.filter(j => j.name.includes(filter))
  return <section className="space-y-2">
    <h2 className="text-xs font-medium">历史记录</h2>
    {!!jobs.length && <input className={FIELD} aria-label="搜索生成记录" placeholder="搜索记录" value={filter} onChange={e => setFilter(e.target.value)} />}
    <div ref={list} className="space-y-1.5">
      {!visible.length && <p className="py-3 text-xs text-ink/45">{jobs.length ? '没有匹配记录' : '生成后的需求和结构会保存在这里'}</p>}
      {visible.map(job => <div key={job.id} className={cn('rounded-md border bg-white p-2', selected === job.id ? 'border-sky-500' : 'border-ink/10')}>
        {editing === job.id ? <form className="flex gap-1" onSubmit={e => { e.preventDefault(); void onRename(job.id, name).then(() => setEditing(null)) }}>
          <input className={FIELD} aria-label="记录名称" maxLength={100} value={name} onChange={e => setName(e.target.value)} />
          <button className={ICON_BUTTON} aria-label="保存名称" disabled={busy || !name.trim()}><Check size={14} /></button>
          <button type="button" className={ICON_BUTTON} aria-label="取消改名" onClick={() => setEditing(null)}><X size={14} /></button>
        </form> : <button className="w-full truncate text-left text-xs font-medium" onClick={() => onSelect(job.id)}>{job.name}</button>}
        <div className="mt-1 flex items-center gap-2 text-[11px] text-ink/55">
          <button className="mr-auto text-left" onClick={() => onSelect(job.id)}>限厚 {job.task.depth} · {job.candidate_count ?? DEFAULT_CANDIDATES} 候选 · {STATUS[job.status]}</button>
          <button className="p-1" title="重命名" aria-label={`重命名 ${job.name}`} disabled={busy} onClick={() => { setEditing(job.id); setName(job.name) }}><Pencil size={13} /></button>
          <button className="p-1 hover:text-red-700" title="删除记录" aria-label={`删除 ${job.name}`} disabled={busy} onClick={() => onRemove(job.id)}><Trash2 size={13} /></button>
        </div>
      </div>)}
    </div>
  </section>
}

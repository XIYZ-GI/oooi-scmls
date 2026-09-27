import { useCallback, useEffect, useRef, useState } from 'react'
import { useAutoAnimate } from '@formkit/auto-animate/react'
import { ArrowLeft, Download, Pause, Play, Plus, Trash2, Upload, X, Brain } from 'lucide-react'
import { Toaster, toast } from 'sonner'
import { OverlayScrollbarsComponent } from 'overlayscrollbars-react'
import { cn } from '@/lib'
import { BUTTON_CLASS, FIELD_CLASS } from '../labeler/constants'
import { searchDownload, searchRequest } from './api'
import { CandidatePreview } from './CandidatePreview'
import { JobSettings } from './JobSettings'
import type { Candidate, CandidateDetail, SearchJob } from './types'

const STATES: Record<string, string> = { queued: '等待运行', running: '搜索中', paused: '已暂停', completed: '已完成', cancelled: '已取消' }
const SPLITS = { train: '训练来源', validation: '验证来源', test: '保留来源' }

export function SearchPage() {
  const [jobs, setJobs] = useState<SearchJob[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [seed, setSeed] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [offset, setOffset] = useState(0)
  const [records, setRecords] = useState<{ total: number; items: Candidate[] }>({ total: 0, items: [] })
  const [detail, setDetail] = useState<CandidateDetail | null>(null)
  const [candidateLoading, setCandidateLoading] = useState(false)
  const [candidateError, setCandidateError] = useState('')
  const [list] = useAutoAnimate<HTMLDivElement>()
  const [candidateList] = useAutoAnimate<HTMLDivElement>()
  const fileInput = useRef<HTMLInputElement>(null)
  const detailRequest = useRef(0)
  const job = jobs.find(j => j.id === selected) ?? jobs[0]

  const reload = useCallback(async () => {
    try {
      const values = await searchRequest<SearchJob[]>('/jobs')
      setJobs(values)
      setError('')
    } catch (cause) { setError((cause as Error).message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    void reload()
    const timer = setInterval(() => void reload(), 4000)
    return () => clearInterval(timer)
  }, [reload])

  const done = job?.seeds.reduce((sum, s) => sum + s.attempted, 0) ?? 0
  useEffect(() => {
    if (!job) return
    let disposed = false
    setCandidateLoading(true)
    const params = new URLSearchParams({ offset: String(offset), limit: '30', accepted_only: String(accepted) })
    if (seed) params.set('seed_id', seed)
    searchRequest<{ total: number; items: Candidate[] }>(`/jobs/${job.id}/candidates?${params}`)
      .then(value => { if (!disposed) { setRecords(value); setCandidateError('') } })
      .catch(cause => { if (!disposed) setCandidateError((cause as Error).message) })
      .finally(() => { if (!disposed) setCandidateLoading(false) })
    return () => { disposed = true }
  }, [job?.id, done, seed, accepted, offset])

  const act = async (action: () => Promise<unknown>, message: string) => {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    try { await action(); await reload(); toast.success(message) }
    catch (cause) { toast.error((cause as Error).message) }
    finally { lock.current = false; setBusy(false) }
  }

  const selectJob = (id: string) => {
    setSelected(id); setSeed(''); setOffset(0); setRecords({ total: 0, items: [] }); setDetail(null); setCreating(false)
    detailRequest.current += 1
  }

  const showCandidate = async (id: number) => {
    if (!job) return
    const version = ++detailRequest.current
    await act(async () => {
      const value = await searchRequest<CandidateDetail>(`/jobs/${job.id}/candidates/${id}`)
      if (version === detailRequest.current) setDetail(value)
    }, '已读取服务器候选')
  }

  const running = job?.state === 'running' || job?.state === 'queued'
  return <div className="min-h-dvh bg-frost text-ink">
    <header className="flex min-h-14 items-center gap-3 border-b border-ink/15 px-3 md:px-6">
      <a className={BUTTON_CLASS} href="#labeler" aria-label="返回打标器"><ArrowLeft size={17} /></a>
      <h1 className="mr-auto text-sm font-semibold">移动线搜索与训练</h1>
      <button className={BUTTON_CLASS} onClick={() => setCreating(v => !v)}><Plus size={17} />新任务</button>
    </header>
    <main className="mx-auto max-w-screen-2xl space-y-4 p-3 md:p-6">
      {loading && <div className="h-24 animate-pulse rounded-md bg-sky-100" aria-label="正在读取服务器任务" />}
      {error && <div className="flex items-center gap-3 text-sm text-red-700" role="alert">{error}<button className={BUTTON_CLASS} onClick={() => void reload()}>重试</button></div>}
      {(creating || (!loading && !error && !jobs.length)) && <section className="space-y-3 border-b border-ink/15 pb-4">
        <p className="text-sm text-ink/60">使用服务器中所有点位齐全、十块负载时序通过的样本。结构与搜索记录均保存到服务器。</p>
        <JobSettings busy={busy} onSubmit={body => act(async () => {
          const value = await searchRequest<SearchJob>('/jobs', 'POST', body)
          selectJob(value.id)
        }, '搜索任务已创建')} />
      </section>}
      <div ref={list} className="flex flex-wrap gap-2">
        {jobs.map(item => <button key={item.id} className={cn(BUTTON_CLASS, item.id === job?.id && 'border-sky-500 bg-sky-50')}
          onClick={() => selectJob(item.id)}>{item.name}<span className="text-xs text-ink/50">{STATES[item.state]}</span></button>)}
      </div>
      {job && <>
        <section className="space-y-3 border-b border-ink/15 pb-4">
          <JobSettings key={`${job.id}:${job.name}:${job.config.per_seed}`} job={job} busy={busy} onSubmit={body => act(
            () => searchRequest(`/jobs/${job.id}`, 'PATCH', running ? { name: body.name } : body), '设置已保存')} />
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-auto text-sm">{STATES[job.state]} · {done}/{job.seeds.length * job.config.per_seed} 个候选 · {job.seeds.reduce((n, s) => n + s.accepted, 0)} 个连续运行通过 · {job.seeds.reduce((n, s) => n + s.improved, 0)} 个更小</span>
            <button className={BUTTON_CLASS} disabled={busy} onClick={() => void act(() => searchRequest(`/jobs/${job.id}`, 'PATCH', { action: running ? 'pause' : 'resume' }), running ? '已暂停，当前候选会保存后停止' : '已继续搜索')}>
              {running ? <Pause size={16} /> : <Play size={16} />}{running ? '暂停' : '继续'}
            </button>
            {running && <button className={BUTTON_CLASS} disabled={busy} onClick={() => void act(() => searchRequest(`/jobs/${job.id}`, 'PATCH', { action: 'cancel' }), '任务已取消')}><X size={16} />取消</button>}
            <button className={BUTTON_CLASS} disabled={busy} onClick={() => void act(() => searchDownload(`/jobs/${job.id}/export`, `${job.name}-训练数据.zip`), '数据包已导出')}><Download size={16} />训练包</button>
            <button className={BUTTON_CLASS} disabled={busy} aria-label="删除任务" onClick={() => void act(async () => {
              const id = job.id
              await searchRequest(`/jobs/${id}`, 'DELETE')
              setSelected(null); setDetail(null); detailRequest.current += 1
              toast('任务已删除，原始样本不受影响', { duration: 15000, action: { label: '撤销', onClick: () => void act(() => searchRequest(`/jobs/${id}/restore`, 'POST'), '任务已恢复') } })
            }, '搜索任务已移除')}><Trash2 size={16} /></button>
          </div>
          {job.error && <p className="text-sm text-amber-800">{job.error}</p>}
          <div className="h-1 overflow-hidden rounded-md bg-ink/10"><div className="h-full bg-sky-500 transition-all" style={{ width: `${Math.min(100, 100 * done / (job.seeds.length * job.config.per_seed))}%` }} /></div>
        </section>
        <section className="flex flex-wrap items-center gap-2 text-sm">
          <Brain size={18} className="text-sky-700" />
          <p className="mr-auto">{job.model?.status === 'trained'
            ? `修改评分器已训练 · ${job.model.trainRows} 条训练记录（正 ${job.model.positive} / 负 ${job.model.negative}）${job.model.external ? ' · AutoDL 模型' : ''}`
            : job.model?.reason ?? '每累计 50 条搜索记录自动训练修改评分器'}
          </p>
          <button className={BUTTON_CLASS} disabled={busy || running || !done} onClick={() => void act(() => searchRequest(`/jobs/${job.id}/train`, 'POST'), '训练状态已更新')}>训练评分器</button>
          <button className={BUTTON_CLASS} disabled={busy || running} onClick={() => fileInput.current?.click()}><Upload size={16} />导入模型</button>
          <input ref={fileInput} type="file" accept=".json" className="hidden" onChange={event => {
            const file = event.target.files?.[0]; event.target.value = ''
            if (file) void act(async () => {
              if (file.size > 1024 * 1024) throw new Error('模型文件不能超过 1 MiB')
              await searchRequest(`/jobs/${job.id}/model`, 'POST', JSON.parse(await file.text()))
            }, '模型已上传，继续任务后用于候选排序')
          }} />
          {job.model?.validation && <p className="w-full text-xs text-ink/55">验证来源 {job.model.validation.rows} 条，准确率 {(job.model.validation.accuracy * 100).toFixed(1)}%，多数类基准 {(job.model.validation.majorityBaseline * 100).toFixed(1)}%。此评分预测首轮负载及时序通过；候选是否可用仍由连续 {job.config.rounds} 轮模拟决定。</p>}
        </section>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <select className={cn(FIELD_CLASS, 'min-w-36 flex-1')} aria-label="按原始样本筛选" value={seed} onChange={event => { setSeed(event.target.value); setOffset(0) }}>
                <option value="">全部 {job.seeds.length} 个来源</option>
                {job.seeds.map(s => <option value={s.id} key={s.id}>{s.name} · {SPLITS[s.split]} · {s.attempted}/{job.config.per_seed}</option>)}
              </select>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={event => { setAccepted(event.target.checked); setOffset(0) }} />仅看连续运行通过</label>
            </div>
            {candidateError && <p className="text-sm text-red-700">{candidateError}</p>}
            <OverlayScrollbarsComponent className="max-h-[65vh]" options={{ scrollbars: { autoHide: 'leave' } }} defer>
            <div ref={candidateList} className="space-y-1" aria-busy={candidateLoading}>
              {!records.items.length && <p className="p-6 text-center text-sm text-ink/50">{candidateLoading ? '正在读取候选…' : '暂无符合条件的候选'}</p>}
              {records.items.map(item => <button key={item.id} className={cn('w-full rounded-md border border-ink/10 bg-white px-3 py-2 text-left text-sm hover:bg-sky-50', detail?.candidate.id === item.id && 'border-sky-500 bg-sky-50')}
                disabled={busy} onClick={() => void showCandidate(item.id)}>
                <span className="flex flex-wrap gap-x-3"><strong className="font-medium">#{item.id} {job.seeds.find(s => s.id === item.seed_id)?.name}</strong><span>{item.edit.label}</span><span>{item.depth} 格厚 · {item.block_count} 块</span>
                  <span className={item.accepted ? 'text-emerald-700' : 'text-ink/50'}>{item.improved ? '通过且更小' : item.accepted ? '连续运行通过' : item.result.load_pass ? '首轮负载通过' : '未通过'}</span></span>
                {!!item.result.reason && <span className="mt-1 block text-xs text-ink/50">{item.result.reason}</span>}
              </button>)}
            </div>
            </OverlayScrollbarsComponent>
            <div className="flex items-center justify-between text-xs">
              <button className={BUTTON_CLASS} disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - 30))}>上一页</button>
              <span>共 {records.total} 条</span>
              <button className={BUTTON_CLASS} disabled={offset + 30 >= records.total} onClick={() => setOffset(v => v + 30)}>下一页</button>
            </div>
          </section>
          <section className="min-w-0">
            {detail && detail.candidate.job_id === job.id ? <>
              <div className="mb-2 flex items-center gap-2 text-sm"><span className="mr-auto">#{detail.candidate.id} · {detail.seed.name} · {detail.candidate.result.rounds.filter(r => r.translation_pass).length}/{job.config.rounds} 轮通过</span>
                <button className={BUTTON_CLASS} disabled={busy} onClick={() => void act(() => searchDownload(`/jobs/${job.id}/candidates/${detail.candidate.id}/export`, `候选${detail.candidate.id}.json`), '结构已导出，可在模拟器导入')}><Download size={16} />结构</button></div>
              <div className="h-[55vh] min-h-80 overflow-hidden rounded-md border border-ink/15"><CandidatePreview key={`${job.id}:${detail.candidate.id}`} detail={detail} /></div>
            </> : <div className="flex min-h-80 items-center justify-center rounded-md border border-ink/10 text-sm text-ink/50">选择候选查看三维结构与原样本对照</div>}
          </section>
        </div>
      </>}
    </main>
    <Toaster position="top-center" richColors closeButton />
  </div>
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import * as bridge from '@/bridge'
import { request } from './api'
import { DEFAULT_TASK, DEFAULT_CANDIDATES, busyJob } from './constants'
import type { Draft, Job, ModelInfo, Task } from './types'

const DEFAULT_MODEL = 'combined-noz-relpos-12d-10.8m'

/** 轮询周期：原生运算在同一台设备上，比走网络时短得多。
 * 运行中盯得紧一些保证进度条跟手，空闲时放慢避免白白唤醒 CPU。 */
const POLL_ACTIVE_MS = 700
const POLL_IDLE_MS = 1800

export function useGenerator() {
  const [task, setTask] = useState<Task>(DEFAULT_TASK)
  const [groupCount, setGroupCount] = useState(1)
  const [candidateCount, setCandidateCount] = useState(DEFAULT_CANDIDATES)
  const [jobs, setJobs] = useState<Job[]>([])
  const [job, setJob] = useState<Job | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [modelId, setModelId] = useState(DEFAULT_MODEL)
  // 权重加载是进页面第一件要看见的事：状态与文案都来自原生侧解包与加载的真实进度。
  const [weightState, setWeightState] = useState<bridge.ModelState>('loading')
  const [weightMessage, setWeightMessage] = useState('正在加载模型权重文件')
  const model = models.find(row => row.id === modelId) ?? null
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [busy, setBusy] = useState(false)
  const revision = useRef(1)
  const saved = useRef('')
  const pending = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const queue = useRef(Promise.resolve())
  const selected = useRef<string | null>(null)
  const selecting = useRef(0)
  const locked = useRef(false)
  const mounted = useRef(true)
  const versions = useRef<Record<string, string>>({})
  const latest = useRef('')
  if (!loading && !error) latest.current = JSON.stringify({ task, group_count: groupCount, candidate_count: candidateCount, model_id: modelId })

  const initialize = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [draft, list, info] = await Promise.all([request<Draft>('/draft'), request<Job[]>('/jobs'), request<{ models: ModelInfo[]; default: string }>('/models')])
      if (!mounted.current) return
      const count = draft.candidate_count ?? DEFAULT_CANDIDATES
      const selectedModel = info.models.some(row => row.id === draft.model_id) ? draft.model_id! : info.default
      saved.current = JSON.stringify({ task: draft.task, group_count: draft.group_count, candidate_count: count, model_id: selectedModel })
      revision.current = draft.revision
      setTask(draft.task); setGroupCount(draft.group_count); setJobs(list); setModels(info.models); setModelId(selectedModel); setSaveError('')
      setCandidateCount(count)
    } catch (e) { if (mounted.current) setError((e as Error).message) }
    finally { if (mounted.current) setLoading(false) }
  }, [])

  useEffect(() => {
    mounted.current = true
    void initialize()
    return () => {
      mounted.current = false
      clearTimeout(pending.current)
      const content = latest.current
      if (content) queue.current = queue.current.then(async () => {
        if (content === saved.current) return
        try {
          const value = await request<Draft>('/draft', 'PUT', { ...JSON.parse(content), revision: revision.current })
          revision.current = value.revision; saved.current = content
        } catch { /* 已卸载的页面不再覆盖远端冲突。 */ }
      })
    }
  }, [initialize])

  useEffect(() => {
    if (loading || error || saveError) return
    const content = JSON.stringify({ task, group_count: groupCount, candidate_count: candidateCount, model_id: modelId })
    if (content === saved.current) return
    setSaving(true)
    pending.current = setTimeout(() => {
      queue.current = queue.current.then(async () => {
        try {
          const value = await request<Draft>('/draft', 'PUT', { ...JSON.parse(content), revision: revision.current })
          revision.current = value.revision; saved.current = content
          if (mounted.current) setSaving(false)
        } catch (e) {
          if (mounted.current) { setSaveError((e as Error).message); setSaving(false) }
        }
      })
    }, 450)
    return () => clearTimeout(pending.current)
  }, [task, groupCount, candidateCount, modelId, loading, error, saveError])

  useEffect(() => {
    if (loading || error) return
    let stopped = false
    let polls = 0
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      let delay = POLL_IDLE_MS
      try {
        const state = bridge.modelState()
        if (stopped) return
        setWeightState(state.state); setWeightMessage(state.message)
        // 模型没就绪时没必要反复读库表，等下一拍再看权重状态即可。
        if (state.state !== 'ready') return
        const list = await request<Job[]>('/jobs')
        if (stopped) return
        setJobs(list)
        if (++polls % 10 === 0) {
          const catalog = await request<{ models: ModelInfo[] }>('/models')
          if (!stopped) setModels(catalog.models)
        }
        const id = selected.current
        const row = list.find(r => r.id === id)
        if (row) {
          if (busyJob(row.status)) delay = POLL_ACTIVE_MS
          setJob(previous => previous?.id === row.id && previous.updated_at === row.updated_at ? previous :
            { ...row, result: previous?.id === row.id ? previous.result : undefined })
          if (!busyJob(row.status) && versions.current[row.id] !== row.updated_at) {
            const detail = await request<Job>(`/jobs/${row.id}`)
            if (!stopped && selected.current === row.id) { versions.current[row.id] = detail.updated_at; setJob(detail) }
          }
        }
      } catch { /* 后续轮询会恢复，初始加载与提交错误单独提示。 */ }
      finally { if (!stopped) timer = setTimeout(() => void poll(), delay) }
    }
    timer = setTimeout(() => void poll(), 400)
    return () => { stopped = true; clearTimeout(timer) }
  }, [loading, error])

  const select = useCallback(async (id: string) => {
    selected.current = id
    const serial = ++selecting.current
    setJob(null)
    try {
      const value = await request<Job>(`/jobs/${id}`)
      if (serial === selecting.current && mounted.current) {
        versions.current[id] = value.updated_at; setJob(value)
        // 打开历史记录时同时载入当时的需求，点画布上的网格按钮即可回到那批目标点继续修改。
        setModelId(models.some(row => row.id === value.model_id) ? value.model_id : DEFAULT_MODEL)
        setCandidateCount(value.candidate_count ?? DEFAULT_CANDIDATES)
        setTask(value.task); setGroupCount(Math.max(1, ...value.task.targets.map(t => t.order)))
      }
    } catch (e) { toast.error((e as Error).message) }
  }, [models])

  const act = async (action: () => Promise<void>) => {
    if (locked.current) return
    locked.current = true; setBusy(true)
    try { await action() } catch (e) { toast.error((e as Error).message) }
    finally { locked.current = false; if (mounted.current) setBusy(false) }
  }

  const generate = () => act(async () => {
    if (!task.targets.length) throw new Error('先在网格上选择目标点')
    if (!model?.ready) throw new Error('所选模型尚未就绪，请重新载入')
    // 删除空组后按先后关系连续编号，界面与实际提交需求同步更新。
    const orders = [...new Set(task.targets.map(t => t.order))].sort((a, b) => a-b)
    const normalized = { ...task, targets: task.targets.map(t => ({ ...t, order: orders.indexOf(t.order)+1 })) }
    setTask(normalized); setGroupCount(orders.length)
    const value = await request<Job>('/jobs', 'POST', { task: normalized, candidate_count: candidateCount, model_id: modelId })
    selected.current = value.id; setJob(value); setJobs(rows => [value, ...rows])
  })

  const cancel = () => act(async () => {
    if (!job) return
    setJob(await request<Job>(`/jobs/${job.id}/cancel`, 'POST')); toast.success('已取消生成')
  })
  const remove = (id: string) => act(async () => {
    await request(`/jobs/${id}`, 'DELETE'); setJobs(rows => rows.filter(r => r.id !== id))
    if (selected.current === id) { selected.current = null; setJob(null); ++selecting.current }
    toast.success('生成记录已删除')
  })
  const rename = (id: string, name: string) => act(async () => {
    const value = await request<Job>(`/jobs/${id}`, 'PATCH', { name })
    setJobs(rows => rows.map(r => r.id === id ? value : r))
    setJob(old => old?.id === id ? { ...old, ...value } : old); toast.success('名称已保存')
  })
  return { task, setTask, groupCount, setGroupCount, candidateCount, setCandidateCount, jobs, job, model, models, modelId, setModelId, loading, error, saving, saveError,
    busy, weightState, weightMessage, initialize, select, generate, cancel, remove, rename, act }
}

import { Suspense, useEffect, useRef, useState } from 'react'
import { Box, CircleAlert, Grid2X2, LoaderCircle, Pause, Play, RefreshCw, RotateCcw, Settings2, SkipForward, Sparkles, X } from 'lucide-react'
import { Drawer } from 'vaul'
import { OverlayScrollbarsComponent } from 'overlayscrollbars-react'
import { motion } from 'framer-motion'
import { Toaster, toast } from 'sonner'
import { cn } from '@/lib'
import { BUTTON, ICON_BUTTON, busyJob } from './constants'
import { download } from './api'
import { useGenerator } from './useGenerator'
import { useReplay } from './useReplay'
import { GenerationScene } from './GenerationScene'
import { GenerationHistory } from './GenerationHistory'
import { ResultPanel } from './ResultPanel'
import { TaskEditor } from './TaskEditor'
import { TaskToolbar } from './TaskToolbar'
import { resizeTask } from './taskEdit'
import { ModelCard } from './ModelCard'
import type { Task } from './types'

export function GeneratorPage() {
  const state = useGenerator()
  const [activeGroup, setActiveGroup] = useState(1)
  const [erase, setErase] = useState(false)
  const [editing, setEditing] = useState(true)
  const [loads, setLoads] = useState(false)
  const [candidate, setCandidate] = useState(0)
  const [camera, setCamera] = useState(0)
  const [drawer, setDrawer] = useState(false)
  const [history, setHistory] = useState<{ task: Task; groups: number }[]>([])
  const completed = useRef('')
  const resizing = useRef<Task | null>(null)
  const latestTask = useRef(state.task)
  latestTask.current = state.task
  const replay = useReplay(state.job?.id, candidate)
  const result = state.job?.result
  const selectedProposal = result?.proposals[candidate]

  useEffect(() => {
    if (!state.job || !result || completed.current === state.job.id) return
    completed.current = state.job.id
    setCandidate(result.selected); setEditing(false); setDrawer(false)
  }, [state.job, result])
  useEffect(() => { if (activeGroup > state.groupCount) setActiveGroup(state.groupCount) }, [activeGroup, state.groupCount])

  const editTask = (next: Task) => {
    setEditing(true); replay.clear()
    setHistory(rows => [...rows.slice(-39), { task: state.task, groups: state.groupCount }])
    state.setTask(next)
  }
  const mark = (x: number, y: number) => {
    if (state.loading || state.error) return
    const previous = state.task.targets.find(t => t.x === x && t.y === y)
    const targets = state.task.targets.filter(t => t.x !== x || t.y !== y)
    if (!erase && previous?.order !== activeGroup) {
      if (targets.length >= 32) { toast.error('最多选择32个目标点'); return }
      targets.push({ x, y, z: 0, order: activeGroup })
    }
    editTask({ ...state.task, targets })
  }
  const selectJob = (id: string) => {
    replay.clear(); completed.current = ''; setEditing(false); setDrawer(false); void state.select(id)
  }
  const submit = () => {
    if (state.busy) return
    replay.clear(); completed.current = ''; setDrawer(false); void state.generate()
  }
  // 拖动网格边缘时连续改尺寸，只在松手时记一条历史，避免撤销栈被刷满。
  const applyResize = (changes: { width?: number; height?: number }, anchor: 'start' | 'end' = 'end') => {
    if (!resizing.current) resizing.current = latestTask.current
    const next = resizeTask(latestTask.current, changes, anchor)
    if (next) { setEditing(true); state.setTask(next) }
  }
  const commitResize = () => {
    const before = resizing.current
    resizing.current = null
    if (before && JSON.stringify(before) !== JSON.stringify(latestTask.current)) {
      setHistory(rows => [...rows.slice(-39), { task: before, groups: state.groupCount }])
    }
  }
  const exportScene = () => void state.act(async () => {
    if (!state.job) return
    // 原生侧直接写出基岩版小端 NBT 结构到系统「下载」目录，网页拿不到也不该拿文件流，
    // 因此把写入后的文件名回显给用户，让他们知道去文件管理器里找什么。
    const name = await download(`/jobs/${state.job.id}/candidates/${candidate}/export?assembly=${loads}`, '移动线.mcstructure')
    toast.success(`结构已导出：${name}`, { description: '文件已保存到手机的「下载」目录' })
  })
  const controls = <div className="space-y-4 p-3">
    {state.saveError && <div className="text-xs text-red-700">{state.saveError}<button className="ml-2 underline" onClick={() => void state.initialize()}>重新载入</button></div>}
    <ModelCard model={state.model} models={state.models} onChange={state.setModelId} state={state.weightState} message={state.weightMessage}
      disabled={state.loading || !!state.error} />
    <TaskEditor task={state.task} disabled={state.loading || !!state.error}
      candidateCount={state.candidateCount} onCandidateCount={state.setCandidateCount} onTask={editTask}
      judgeOnly={!!state.model?.conditioning &&
        (!state.model.conditioning.max_ticks || !state.model.conditioning.rounds)} />
    <button className={cn(BUTTON, 'h-10 w-full border-sky-600 bg-sky-600 font-medium text-white hover:bg-sky-700')}
      disabled={state.busy || state.loading || !!state.error || !state.model?.ready || !state.task.targets.length}
      onClick={submit}>
      {state.busy ? <LoaderCircle size={16} className="animate-spin" /> : <Sparkles size={16} />}生成移动线
    </button>
    {state.model && !state.model.ready && <p className="text-xs text-red-700">模型文件尚未就绪</p>}
    {state.job && <ResultPanel job={state.job} candidate={candidate} busy={state.busy} onCandidate={i => { setCandidate(i); setEditing(false); setDrawer(false) }}
      onCancel={() => void state.cancel()} />}
    <GenerationHistory jobs={state.jobs} selected={state.job?.id} busy={state.busy} onSelect={selectJob} onRemove={id => void state.remove(id)} onRename={state.rename} />
  </div>

  return <div className="flex h-dvh min-w-0 flex-col overflow-hidden bg-frost text-ink">
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-ink/15 px-3">
      <h1 className="mr-auto truncate text-sm font-semibold">移动线生成</h1>
      <Drawer.Root open={drawer} onOpenChange={setDrawer}>
        <Drawer.Trigger className={cn(ICON_BUTTON, 'md:hidden')} aria-label="配置"><Settings2 size={16} /></Drawer.Trigger>
        <Drawer.Portal><Drawer.Overlay className="fixed inset-0 z-50 bg-ink/30" /><Drawer.Content className="fixed inset-x-0 bottom-0 z-50 flex max-h-[86dvh] flex-col rounded-t-lg bg-frost outline-none">
          <div className="flex shrink-0 items-center justify-between border-b border-ink/10 p-3"><Drawer.Title className="text-sm font-medium">配置</Drawer.Title><Drawer.Close className={ICON_BUTTON} aria-label="关闭"><X size={16} /></Drawer.Close></div>
          <Drawer.Description className="sr-only">编辑网格、时序组和生成参数，查看服务器上的生成记录。</Drawer.Description>
          <OverlayScrollbarsComponent className="min-h-0 overflow-auto" options={{ scrollbars: { autoHide: 'leave' } }}>{controls}</OverlayScrollbarsComponent>
        </Drawer.Content></Drawer.Portal>
      </Drawer.Root>
    </header>
    <main className="flex min-h-0 flex-1">
      <aside className="hidden w-[292px] shrink-0 border-r border-ink/15 md:flex">
        <OverlayScrollbarsComponent className="h-full w-full" options={{ scrollbars: { autoHide: 'leave' } }}>{controls}</OverlayScrollbarsComponent>
      </aside>
      <section className="flex min-h-0 min-w-0 flex-1 flex-col" aria-label="移动线生成三维工作区">
        <TaskToolbar task={state.task} groups={state.groupCount} active={activeGroup} erase={erase}
          disabled={state.loading || !!state.error} canUndo={!!history.length}
          exportDisabled={state.busy || !selectedProposal} onExport={exportScene}
          onTask={editTask} onGroups={state.setGroupCount}
          onActive={group => { setActiveGroup(group); setEditing(true); replay.clear() }}
          onErase={value => { setErase(value); setEditing(true); replay.clear() }}
          onClear={() => editTask({ ...state.task, targets: [] })}
          onUndo={() => { const previous = history.at(-1); if (previous) { setEditing(true); replay.clear(); state.setTask(previous.task); state.setGroupCount(previous.groups); setHistory(rows => rows.slice(0, -1)) } }} />
        {state.job && busyJob(state.job.status) && <div className="flex shrink-0 items-center gap-2 border-b border-ink/15 bg-frost px-2 py-1.5">
          <span className="shrink-0 text-[11px] text-ink/55">生成中</span>
          <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded bg-sky-100" role="progressbar"
            aria-label="生成总进度" aria-valuenow={state.job.progress} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-sky-500 transition-all" style={{ width: `${state.job.progress}%` }} />
          </div>
          <span className="shrink-0 text-[11px] tabular-nums text-ink/60">{state.job.progress}%</span>
        </div>}
        {state.loading ? <div className="flex flex-1 animate-pulse items-center justify-center bg-bench text-sm text-ink/50">正在读取本机需求…</div> : state.error ?
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-4 text-sm"><p>{state.error}</p><button className={BUTTON} onClick={() => void state.initialize()}><RefreshCw size={14} />重新连接</button></div> :
          state.weightState !== 'ready' ? <div className="flex flex-1 flex-col items-center justify-center gap-3 bg-bench p-6 text-center">
            {state.weightState === 'error' ? <CircleAlert size={22} className="text-red-700" /> : <LoaderCircle size={22} className="animate-spin text-sky-600" />}
            <p className="text-sm">{state.weightState === 'error' ? '模型权重加载失败' : '正在加载模型权重文件'}</p>
            <p className="max-w-xs text-xs text-ink/55">{state.weightMessage || '首次启动需要把权重从安装包解包到本机存储，请稍候'}</p>
          </div> :
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-0 flex-1 bg-bench">
            <Suspense fallback={<div className="h-full animate-pulse bg-bench" />}>
              <GenerationScene task={editing ? state.task : state.job?.task ?? state.task}
                loadTask={!editing ? result?.load_tasks?.[candidate] : undefined} editing={editing || !selectedProposal}
                proposal={selectedProposal} loads={loads} frame={!editing ? replay.replay?.trace[replay.index]?.snapshot : undefined}
                initial={replay.replay?.trace[0]?.snapshot} onMark={mark} onResize={applyResize}
                onResizeCommit={commitResize} resetKey={camera} />
            </Suspense>
          </motion.div>}

        <div className="flex h-11 shrink-0 items-center gap-1 border-t border-ink/15 bg-frost px-2">
          <button className={cn(ICON_BUTTON, editing && 'border-sky-500')} aria-label="编辑目标" title="编辑目标" onClick={() => { setEditing(true); replay.pause() }}><Grid2X2 size={16} /></button>
          <button className={cn(ICON_BUTTON, !editing && 'border-sky-500')} disabled={!selectedProposal} aria-label="查看生成结构" title="查看生成结构" onClick={() => setEditing(false)}><Box size={16} /></button>
          <button className={cn(ICON_BUTTON, loads && 'border-sky-500')} disabled={editing || !selectedProposal || !!replay.replay} aria-label="显示或隐藏十块负载" title="十块负载" onClick={() => setLoads(v => !v)}><span className="text-[11px] font-medium">10</span></button>
          <button className={ICON_BUTTON} disabled={editing || !selectedProposal || replay.loading} aria-label={replay.playing ? '暂停回放' : '播放运行回放'} title={replay.playing ? '暂停' : '播放回放'} onClick={() => void replay.start(true)}>
            {replay.loading ? <LoaderCircle size={15} className="animate-spin" /> : replay.playing ? <Pause size={15} /> : <Play size={15} />}</button>
          <button className={ICON_BUTTON} disabled={editing || !selectedProposal || replay.loading} aria-label="前进一刻" title="前进一刻" onClick={() => void replay.start(false)}><SkipForward size={15} /></button>
          <button className={ICON_BUTTON} disabled={!replay.replay || editing} aria-label="回放复位" title="回放复位" onClick={replay.reset}><RotateCcw size={15} /></button>
          <button className={ICON_BUTTON} aria-label="重置视角" title="重置视角" onClick={() => setCamera(v => v+1)}><RefreshCw size={15} /></button>
          <span className="ml-auto min-w-0 truncate text-[11px] text-ink/55">{state.job && busyJob(state.job.status) ? `${state.job.progress}%` : !editing && replay.replay ? `${replay.replay.trace[replay.index]?.snapshot.tick ?? 0} 刻` : !editing && result ? result.evaluations[candidate]?.accepted ? '通过' : result.evaluations[candidate]?.partial ? '半通过' : '未通过' : erase ? '擦除' : ''}</span>
          <button className={cn(ICON_BUTTON, 'border-sky-600 bg-sky-600 text-white hover:bg-sky-700')}
            aria-label="生成移动线" title="按当前需求生成移动线"
            disabled={state.busy || state.loading || !!state.error} onClick={submit}>
            {state.busy ? <LoaderCircle size={16} className="animate-spin" /> : <Sparkles size={16} />}
          </button>
        </div>
      </section>
    </main>
    <Toaster position="top-center" richColors closeButton />
  </div>
}

import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Download,
  FileBox,
  FolderInput,
  List,
  LoaderCircle,
  SlidersHorizontal,
  Upload,
  Brain,
  Sparkles,
} from 'lucide-react'
import { OverlayScrollbarsComponent } from 'overlayscrollbars-react'
import { useMemo, useRef, useState } from 'react'
import { Toaster, toast } from 'sonner'
import { AnnotationPanel, AnnotationScene, SampleList } from './components'
import { LabelDrawer } from './components/LabelDrawer'
import { BUTTON_CLASS } from './constants'
import { useAutomaticTiming, useLabelLibrary } from './hooks'
import { importStructureFile, downloadDataset, uploadDataset } from './services'
import type { ImportFailure, LabelSample, MarkTool, TargetPoint } from './types'
import { normalizeStructure, defaultTargetDepth, columnRear } from './utils'
import type { Direction } from '@/types'

export function LabelerPage() {
  const library = useLabelLibrary()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [tool, setTool] = useState<MarkTool>('target')
  const [progress, setProgress] = useState<string | null>(null)
  const [failures, setFailures] = useState<ImportFailure[]>([])
  const [focus, setFocus] = useState<{ sampleId: string; point: TargetPoint } | null>(null)
  const importLock = useRef(false)
  const structuresInput = useRef<HTMLInputElement>(null)
  const jsonInput = useRef<HTMLInputElement>(null)
  const sample =
    library.samples.find((item) => item.id === selectedId) ??
    library.samples[0] ??
    null
  const shape = useMemo(
    () => (sample ? normalizeStructure(sample) : null),
    [sample],
  )
  const calculation = useAutomaticTiming(sample, library.compute)
  const index = sample
    ? library.samples.findIndex((item) => item.id === sample.id)
    : -1

  const importFiles = async (files: File[]) => {
    if (importLock.current || !files.length) return
    importLock.current = true
    setFailures([])
    const errors: ImportFailure[] = []
    const imported: LabelSample[] = []
    let added = 0
    try {
      for (const [fileIndex, file] of files.entries()) {
        setProgress(`正在导入 ${fileIndex + 1}/${files.length}：${file.name}`)
        try {
          const result = await importStructureFile(file)
          result.items.forEach(library.accept)
          imported.push(...result.items)
          added += result.added
        } catch (cause) {
          errors.push({
            file: file.name,
            reason: cause instanceof Error ? cause.message : '导入失败',
          })
        }
      }
      if (imported[0]) setSelectedId(imported[0].id)
      setFailures(errors)
      if (added)
        toast.success(
          `已上传 ${added} 个移动线${imported.length > added ? `，合并 ${imported.length - added} 个重复结构` : ''}`,
        )
      else if (imported.length) toast.info('所选结构已经导入，已跳过重复项')
      if (errors.length)
        toast.error(`${errors.length} 个文件导入失败，请查看错误详情`)
    } finally {
      setProgress(null)
      importLock.current = false
    }
  }

  const restoreDataset = async (file: File) => {
    if (importLock.current) return
    importLock.current = true
    setProgress('正在恢复 JSON 数据集…')
    try {
      if (file.size > 64 * 1024 * 1024)
        throw new Error('JSON 文件不能超过 64 MiB')
      const result = await uploadDataset(file)
      result.items.forEach(library.accept)
      if (result.items[0]) setSelectedId(result.items[0].id)
      toast.success(`已恢复 ${result.added} 个样本，同名样本已自动编号`)
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : '恢复失败')
    } finally {
      setProgress(null)
      importLock.current = false
    }
  }

  const setForward = async (forward: Direction) => {
    if (!sample) return
    if (sample.forward === forward) {
      if (await library.flush()) toast.info('当前前进方向已与视角一致')
      return
    }
    const previous = { forward: sample.forward, targets: sample.targets, pushPoint: sample.pushPoint, completed: sample.completed }
    library.update(sample.id, { forward, targets: [], pushPoint: null, completed: false })
    const saved = await library.flush()
    toast[saved ? 'success' : 'error'](saved ? '前进方向已保存，原点标注已清空' : '方向尚未保存到服务器，请重试保存', {
      duration: 15000,
      action: { label: '撤销', onClick: () => {
        library.update(sample.id, previous)
        void library.flush()
      } },
    })
  }

  const mark = (x: number, y: number, clickedZ?: number) => {
    if (!sample || !shape) return
    if (tool === 'push') {
      const rear = columnRear(shape, { x, y })
      if (rear === null) {
        toast.error('此位置没有可从后方接触的移动线方块')
        return
      }
      if (clickedZ !== undefined && clickedZ !== rear) {
        toast.error('这个方块后方还有方块，不能作为推动点')
        return
      }
      library.update(sample.id, { pushPoint: { x, y, z: rear }, completed: false })
    } else if (tool === 'target') {
      library.update(sample.id, {
        completed: false,
        targets: [
          ...sample.targets.filter((point) => point.x !== x || point.y !== y),
          sample.targets.find((point) => point.x === x && point.y === y) ?? { x, y, z: defaultTargetDepth(shape, { x, y }) },
        ],
      })
    } else {
      library.update(sample.id, {
        completed: false,
        targets: sample.targets.filter(
          (point) => point.x !== x || point.y !== y,
        ),
        pushPoint:
          sample.pushPoint?.x === x && sample.pushPoint?.y === y
            ? null
            : sample.pushPoint,
      })
    }
  }

  const list = (
    <SampleList
      samples={library.samples}
      selectedId={sample?.id ?? null}
      onSelect={setSelectedId}
    />
  )
  const panel =
    sample && shape ? (
      <AnnotationPanel
        key={sample.id}
        sample={sample}
        shape={shape}
        tool={tool}
        onTool={setTool}
        calculation={calculation}
        onMark={mark}
        onUpdate={(patch) => library.update(sample.id, patch)}
        onRename={(name) => library.rename(sample.id, name)}
        onRemove={() => library.remove(sample.id)}
        onSave={library.flush}
        onFocus={(point) => setFocus({ sampleId: sample.id, point: { ...point } })}
      />
    ) : null

  return (
    <div className="flex h-dvh w-full min-w-0 flex-col overflow-hidden bg-frost text-ink">
      <header className="flex min-h-14 shrink-0 items-center gap-1 border-b border-ink/15 px-2 max-sm:[&>a]:!px-2 max-sm:[&>button]:!px-2 sm:gap-2 md:px-4">
        <a
          href="#"
          aria-label="返回模拟器"
          title="返回模拟器"
          className={`${BUTTON_CLASS} px-2`}
          onClick={async (event) => {
            event.preventDefault()
            if (await library.flush()) window.location.hash = ''
          }}
        >
          <ArrowLeft size={18} />
        </a>
        <h1 className="mr-auto whitespace-nowrap text-sm font-semibold">
          移动线打标器
        </h1>
        <a href="#generate" className={`${BUTTON_CLASS} px-2`} aria-label="AI 移动线生成" title="AI 移动线生成"
          onClick={async event => { event.preventDefault(); if (await library.flush()) window.location.hash = '#generate' }}>
          <Sparkles size={17} />
        </a>
        <a href="#search" className={`${BUTTON_CLASS} px-2`} aria-label="搜索与训练" title="搜索与训练"
          onClick={async event => { event.preventDefault(); if (await library.flush()) window.location.hash = '#search' }}>
          <Brain size={17} /><span className="hidden sm:inline">搜索训练</span>
        </a>
        <input
          ref={structuresInput}
          type="file"
          accept=".mcstructure"
          multiple
          className="hidden"
          aria-label="批量选择移动线文件"
          onChange={(event) => {
            void importFiles(Array.from(event.target.files ?? []))
            event.target.value = ''
          }}
        />
        <input
          ref={jsonInput}
          type="file"
          accept=".json"
          className="hidden"
          aria-label="选择标注备份文件"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void restoreDataset(file)
            event.target.value = ''
          }}
        />
        <button
          className={`${BUTTON_CLASS} px-2 md:px-3`}
          aria-label="批量导入移动线"
          disabled={!!progress || library.loading || !!library.error}
          onClick={() => structuresInput.current?.click()}
        >
          <Upload size={17} />
          <span className="hidden sm:inline">批量导入</span>
        </button>
        <button
          className={`${BUTTON_CLASS} px-2 md:px-3`}
          aria-label="恢复标注备份"
          disabled={!!progress || library.loading || !!library.error}
          onClick={() => jsonInput.current?.click()}
        >
          <FolderInput size={17} />
          <span className="hidden md:inline">恢复备份</span>
        </button>
        <button
          className={`${BUTTON_CLASS} px-2 md:px-3`}
          aria-label="导出全部标注"
          disabled={!library.samples.length || !!progress}
          onClick={async () => {
            try {
              if (!(await library.flush())) return
              await downloadDataset(library.samples, '移动线标注数据集.json', true)
              toast.success('全部样本及标注已导出')
            } catch (error) { toast.error((error as Error).message) }
          }}
        >
          <Download size={17} />
          <span className="hidden sm:inline">导出全部</span>
        </button>
      </header>
      <div className="flex min-h-10 shrink-0 items-center gap-2 border-b border-ink/10 px-3 text-xs">
        <span className="min-w-0 flex-1 truncate" role="status">
          {progress ??
            (library.saveState === 'pending'
              ? '正在保存到服务器…'
              : library.saveState === 'error'
                ? library.saveError ?? '服务器保存失败，请重试'
                : '结构和标注已保存在服务器')}
        </span>
        {library.saveState === 'error' && (
          <button className={BUTTON_CLASS} onClick={() => void library.discardAndReload()}>
            放弃修改并重新读取
          </button>
        )}
        {library.saveState === 'error' && (
          <button className={BUTTON_CLASS} onClick={() => void library.flush()}>
            重试保存
          </button>
        )}
        {sample && (
          <>
            <button
              className="flex h-10 w-9 items-center justify-center disabled:opacity-30"
              aria-label="上一个样本"
              disabled={index <= 0}
              onClick={() => setSelectedId(library.samples[index - 1].id)}
            >
              <ChevronLeft size={18} />
            </button>
            <span>
              {index + 1}/{library.samples.length}
            </span>
            <button
              className="flex h-10 w-9 items-center justify-center disabled:opacity-30"
              aria-label="下一个样本"
              disabled={index >= library.samples.length - 1}
              onClick={() => setSelectedId(library.samples[index + 1].id)}
            >
              <ChevronRight size={18} />
            </button>
          </>
        )}
      </div>
      {!!failures.length && (
        <details className="max-h-40 shrink-0 overflow-auto border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-950">
          <summary className="cursor-pointer">
            {failures.length} 个文件导入失败，展开查看
          </summary>
          {failures.map((failure, i) => (
            <p key={i} className="mt-2 break-all">
              {failure.file}：{failure.reason}
            </p>
          ))}
        </details>
      )}
      {library.loading ? (
        <div className="flex flex-1 animate-pulse items-center justify-center gap-2 text-sm">
          <LoaderCircle size={18} className="animate-spin" />
          正在读取标注…
        </div>
      ) : library.error ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-sm">
          <p>{library.error}</p>
          <button
            className={BUTTON_CLASS}
            onClick={() => void library.reload()}
          >
            重新读取
          </button>
        </div>
      ) : (
        <main className="relative grid min-h-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[260px_minmax(0,1fr)_360px]">
          <OverlayScrollbarsComponent
            className="hidden min-h-0 border-r border-ink/15 lg:block"
            options={{ scrollbars: { autoHide: 'leave' } }}
            defer
          >
            {list}
          </OverlayScrollbarsComponent>
          {sample && shape ? (
            <div className="min-h-0 min-w-0">
              <AnnotationScene
                key={`${sample.id}:${sample.forward}`}
                sample={sample}
                shape={shape}
                onMark={mark}
                onForward={setForward}
                tool={tool}
                onTool={setTool}
                compute={library.compute}
                maxTicks={calculation.maxTicks}
                calculationBusy={calculation.phase === 'waiting' || calculation.phase === 'running'}
                focus={focus?.sampleId === sample.id ? focus.point : null}
                onResetFocus={() => setFocus(null)}
                mobileActions={<>
                  <LabelDrawer compact label="样本列表" icon={<List size={16} />}>{list}</LabelDrawer>
                  {panel && <LabelDrawer compact label="标注面板" icon={<SlidersHorizontal size={16} />}>{panel}</LabelDrawer>}
                </>}
              />
            </div>
          ) : (
            <div className="flex min-w-0 flex-col items-center justify-center px-6 pb-16 text-center">
              <FileBox size={36} strokeWidth={1.4} className="text-sky-700" />
              <h2 className="mt-5 text-lg font-medium">
                导入你已经整理好的移动线
              </h2>
              <p className="mt-2 max-w-sm text-sm leading-6 text-ink/60">
                一次选择多个 .mcstructure
                文件，逐个查看三维模型，标记推动点和目标点，模拟器自动提取时序。
              </p>
              <button
                className={`${BUTTON_CLASS} mt-6 border-sky-400 bg-sky-100`}
                disabled={!!progress}
                onClick={() => structuresInput.current?.click()}
              >
                <Upload size={17} />
                选择结构文件
              </button>
              <p className="mt-3 text-xs text-ink/45">
                原始文件上传服务器，结构和标注跨设备共享。
              </p>
            </div>
          )}
          <OverlayScrollbarsComponent
            className="hidden min-h-0 border-l border-ink/15 lg:block"
            options={{ scrollbars: { autoHide: 'leave' } }}
            defer
          >
            {panel ?? (
              <p className="p-4 text-sm text-ink/50">选择样本后开始标注。</p>
            )}
          </OverlayScrollbarsComponent>
          {!sample && <div className="absolute inset-x-0 bottom-1 flex h-11 justify-center gap-0.5 lg:hidden">
            <LabelDrawer label="样本列表" icon={<List size={17} />}>
              {list}
            </LabelDrawer>
            {panel && (
              <LabelDrawer
                label="标注面板"
                icon={<SlidersHorizontal size={17} />}
              >
                {panel}
              </LabelDrawer>
            )}
          </div>}
        </main>
      )}
      <Toaster position="top-center" richColors closeButton />
    </div>
  )
}

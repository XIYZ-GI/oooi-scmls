import { Check, Download, Pencil, Save, Trash2, Undo2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import type { LabelSample, MarkTool, NormalizedStructure, TargetPoint } from '../types'
import { annotationError } from '../utils'
import { BUTTON_CLASS, FIELD_CLASS } from '../constants'
import { downloadDataset } from '../services'
import { downloadServerFile } from '@/lib/serverLibrary'
import { SectionGrid } from './SectionGrid'
import { TimingPanel } from './TimingPanel'
import { TargetList } from './TargetList'
import type { useAutomaticTiming } from '../hooks/useAutomaticTiming'

export function AnnotationPanel({
  sample,
  shape,
  tool,
  onTool,
  onMark,
  onUpdate,
  onRename,
  onRemove,
  onSave,
  calculation,
  onFocus,
}: {
  calculation: ReturnType<typeof useAutomaticTiming>
  sample: LabelSample
  shape: NormalizedStructure
  tool: MarkTool
  onTool: (tool: MarkTool) => void
  onMark: (x: number, y: number) => void
  onUpdate: (patch: Partial<LabelSample>) => void
  onRename: (name: string) => void
  onRemove: () => void
  onSave: () => Promise<boolean>
  onFocus: (point: TargetPoint) => void
}) {
  const [name, setName] = useState(sample.name)
  const [saving, setSaving] = useState(false)
  const issue = annotationError(sample)
  const unsupported = [
    ...new Set(
      sample.blocks
        .filter((block) => !block.kind || block.layer !== 0)
        .map((block) => block.name),
    ),
  ]
  const save = async () => {
    if (saving) return
    setSaving(true)
    if (await onSave()) toast.success('标注已保存到服务器')
    setSaving(false)
  }
  return (
    <div className="space-y-5 p-4">
      <form
        className="flex items-end gap-2"
        onSubmit={async (event) => {
          event.preventDefault()
          try {
            onRename(name)
            if (await onSave()) toast.success('名称已保存到服务器')
          } catch (error) {
            toast.error((error as Error).message)
          }
        }}
      >
        <label className="min-w-0 flex-1 space-y-1 text-xs text-ink/60">
          样本名称
          <input
            aria-label="样本名称"
            maxLength={120}
            className={FIELD_CLASS}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <button type="submit" aria-label="重命名样本" className={BUTTON_CLASS}>
          <Pencil size={16} />
        </button>
      </form>
      <SectionGrid
        sample={sample}
        shape={shape}
        tool={tool}
        onTool={onTool}
        onMark={onMark}
      />
      <div className="flex items-center justify-between border-y border-ink/10 py-2 text-sm">
        <span>
          推动点：
          {sample.pushPoint
            ? `(${sample.pushPoint.x}, ${sample.pushPoint.y})`
            : '未标注'}
        </span>
        <button
          type="button"
          aria-label="删除推动点"
          disabled={!sample.pushPoint}
          className={BUTTON_CLASS}
          onClick={() => onUpdate({ pushPoint: null, completed: false })}
        >
          <Trash2 size={14} />
        </button>
      </div>
      <TargetList sample={sample} shape={shape} onUpdate={onUpdate} onFocus={onFocus} />
      <TimingPanel sample={sample} calculation={calculation} />
      <label className="block space-y-1 text-xs text-ink/60">
        作者 / 来源
        <input
          aria-label="作者或来源"
          className={FIELD_CLASS}
          value={sample.author}
          maxLength={300}
          onChange={(event) => onUpdate({ author: event.target.value })}
        />
      </label>
      <label className="block space-y-1 text-xs text-ink/60">
        备注
        <textarea
          aria-label="样本备注"
          className={`${FIELD_CLASS} h-20 resize-y py-2`}
          value={sample.notes}
          maxLength={5000}
          onChange={(event) => onUpdate({ notes: event.target.value })}
        />
      </label>
      {!!unsupported.length && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
          以下方块或附加层使用棕色占位显示，原始名称、状态和坐标会完整导出：
          <p className="break-all">{unsupported.join('、')}</p>
        </div>
      )}
      <div className="space-y-2 border-t border-ink/15 pt-4">
        {issue && <p className="text-xs text-ink/60">待完成：{issue}</p>}
        <button
          className={`${BUTTON_CLASS} w-full border-sky-400 bg-sky-100`}
          disabled={!sample.completed && !!issue}
          onClick={async () => {
            onUpdate({ completed: !sample.completed })
            if (await onSave()) toast.success(sample.completed ? '已恢复为待标注' : '已标记完成')
          }}
        >
          {sample.completed ? <Undo2 size={16} /> : <Check size={16} />}
          {sample.completed ? '恢复为待标注' : '标记完成'}
        </button>
        <div className="grid grid-cols-2 gap-2">
          <button
            className={BUTTON_CLASS}
            disabled={saving}
            onClick={() => void save()}
          >
            <Save size={15} />
            {saving ? '保存中…' : '立即保存'}
          </button>
          <button
            className={BUTTON_CLASS}
            onClick={async () => {
              try {
                if (!(await onSave())) return
                await downloadDataset([sample], `${sample.name}.json`)
                toast.success('样本已导出')
              } catch (error) { toast.error((error as Error).message) }
            }}
          >
            <Download size={15} />
            导出样本
          </button>
        </div>
        <button
          className={`${BUTTON_CLASS} w-full text-red-700`}
          onClick={onRemove}
        >
          <Trash2 size={15} />
          删除样本
        </button>
        {sample.originals?.map((file) => (
          <button key={file.id} className={`${BUTTON_CLASS} w-full min-w-0`} onClick={() => {
            void downloadServerFile(`samples/${sample.id}/original/${file.id}`, file.filename).catch((error) => toast.error(error.message))
          }}>
            <Download size={15} className="shrink-0" />
            <span className="truncate">{file.filename}</span>
          </button>
        ))}
        {!sample.originals?.length && <p className="text-xs text-ink/55">结构数据已存服务器；补传原始文件后可下载 .mcstructure。</p>}
        <p className="break-all text-[11px] text-ink/45">
          原文件：{sample.fileName}
          <br />
          “完成”表示点标注完成；模拟时序另行记录。
        </p>
      </div>
    </div>
  )
}

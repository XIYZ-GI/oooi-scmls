import { useAutoAnimate } from '@formkit/auto-animate/react'
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  CheckSquare2,
  Download,
  FolderOpen,
  GripVertical,
  Pencil,
  Save,
  Square,
  Trash2,
  Upload,
} from 'lucide-react'
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'

import type { StoredScene } from '@/hooks'
import { cn } from '@/lib'
import { downloadServerFile } from '@/lib/serverLibrary'
import type { WorldBlockInput } from '@/types'

interface SceneManagerProps {
  scenes: StoredScene[]
  currentBlocks: WorldBlockInput[]
  disabled?: boolean
  loading: boolean
  error: string | null
  onReload: () => Promise<void>
  onImport: (file: File) => Promise<StoredScene>
  onCreate: (name: string, blocks: WorldBlockInput[]) => Promise<StoredScene>
  onUpdate: (id: string, blocks: WorldBlockInput[]) => Promise<void>
  onRename: (id: string, name: string) => Promise<void>
  onRemove: (id: string) => Promise<StoredScene | null>
  onRemoveMany: (ids: string[]) => Promise<StoredScene[]>
  onRestore: (scene: StoredScene) => Promise<void>
  onReorder: (activeId: string, overId: string) => Promise<void>
  onLoad: (scene: StoredScene) => void
}

export function SceneManager(props: SceneManagerProps) {
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const selectedSet = useMemo(() => new Set(selected), [selected])
  const allSelected = props.scenes.length > 0 && selected.length === props.scenes.length
  const [parent] = useAutoAnimate<HTMLDivElement>({ duration: 170 })
  const fileInput = useRef<HTMLInputElement>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))

  const createScene = async (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      const fallback = `结构 ${props.scenes.length + 1}`
      await props.onCreate(name.trim() || fallback, props.currentBlocks)
      setName('')
      toast.success('结构已保存到服务器')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '结构保存失败')
    } finally { setBusy(false) }
  }

  useEffect(() => {
    const alive = new Set(props.scenes.map((scene) => scene.id))
    setSelected((values) => values.filter((id) => alive.has(id)))
  }, [props.scenes])

  const toggleSelect = (id: string) => {
    setSelected((values) => values.includes(id) ? values.filter((value) => value !== id) : [...values, id])
  }

  const removeSelected = async () => {
    if (busy || selected.length === 0) return
    setBusy(true)
    try {
      const removed = await props.onRemoveMany(selected)
      setSelected([])
      if (removed.length) {
        toast(`${removed.length} 个结构已删除`, {
          action: {
            label: '撤销',
            onClick: () => {
              void Promise.all(removed.map((scene) => props.onRestore(scene)))
                .then(() => toast.success('已恢复删除的结构'))
                .catch((error: Error) => toast.error(error.message))
            },
          },
        })
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '批量删除失败')
    } finally { setBusy(false) }
  }

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (over && active.id !== over.id) void props.onReorder(String(active.id), String(over.id)).catch((error) => toast.error(error.message))
  }

  const importScene = async (file: File) => {
    if (busy) return
    setBusy(true)
    try {
      const scene = await props.onImport(file)
      props.onLoad(scene)
      toast.success('结构已上传到服务器')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '结构导入失败')
    } finally { setBusy(false) }
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col border-t border-ink/15">
      <div className="flex items-center px-3 py-2.5">
        <h2 className="text-[11px] font-semibold text-ink/55">服务器结构{busy ? ' · 保存中…' : ''}</h2>
        <button
          type="button"
          aria-label="导入结构"
          disabled={props.disabled || busy}
          onClick={() => fileInput.current?.click()}
          className="ml-auto flex h-8 w-8 items-center justify-center text-ink/55 hover:bg-white disabled:opacity-35"
        >
          <Upload size={15} />
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void importScene(file)
            event.target.value = ''
          }}
        />
      </div>
      {props.scenes.length > 0 && (
        <div className="flex items-center gap-1.5 px-3 pb-2">
          <button
            type="button"
            disabled={props.disabled || busy}
            onClick={() => setSelected(allSelected ? [] : props.scenes.map((scene) => scene.id))}
            className="flex h-8 items-center gap-1 border border-ink/15 bg-white/60 px-2 text-[11px] text-ink/70 hover:bg-white disabled:opacity-35"
          >
            {allSelected ? <CheckSquare2 size={13} /> : <Square size={13} />}
            {allSelected ? '取消全选' : '全选'}
          </button>
          <button
            type="button"
            disabled={props.disabled || busy || selected.length === 0}
            onClick={() => void removeSelected()}
            className="flex h-8 items-center gap-1 border border-ink/15 bg-white/60 px-2 text-[11px] text-ink/70 hover:bg-white hover:text-signal disabled:opacity-35"
          >
            <Trash2 size={13} />
            批量删除{selected.length ? ` (${selected.length})` : ''}
          </button>
        </div>
      )}
      <form onSubmit={createScene} className="flex gap-1.5 px-3 pb-3">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={props.disabled || busy}
          maxLength={40}
          aria-label="结构名称"
          placeholder={`结构 ${props.scenes.length + 1}`}
          className="h-9 min-w-0 flex-1 border border-ink/15 bg-white/60 px-2.5 text-xs text-ink outline-none focus:border-ink disabled:opacity-40"
        />
        <button
          type="submit"
          aria-label="保存新结构"
          disabled={props.disabled || busy}
          className="flex h-9 w-9 items-center justify-center border border-ink/15 bg-white/60 text-ink hover:bg-white disabled:opacity-35"
        >
          <Save size={15} />
        </button>
      </form>
      <div ref={parent} className="min-h-0 flex-1 overflow-y-auto">
        {props.error && <div className="px-3 py-2 text-xs text-red-700">{props.error}<button className="mt-2 block min-h-10 underline" onClick={() => void props.onReload()}>放弃未保存修改并重新读取</button></div>}
        {props.loading ? <p className="animate-pulse px-3 py-5 text-xs">正在读取服务器结构…</p> : props.scenes.length === 0 ? (
          <div className="px-3 py-5 text-xs text-ink/40">没有已保存结构</div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={props.scenes.map((scene) => scene.id)} strategy={verticalListSortingStrategy}>
              {props.scenes.map((scene) => (
                <SceneRow key={scene.id} scene={scene} selected={selectedSet.has(scene.id)}
                  onToggleSelect={toggleSelect} {...props} />
              ))}
            </SortableContext>
          </DndContext>
        )}
      </div>
    </section>
  )
}

function SceneRow(props: SceneManagerProps & { scene: StoredScene; selected: boolean; onToggleSelect: (id: string) => void }) {
  const operation = useRef(false)
  const [busy, setBusy] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(props.scene.name)
  const sortable = useSortable({ id: props.scene.id, disabled: props.disabled })
  const style = {
    transform: CSS.Transform.toString(sortable.transform),
    transition: sortable.transition,
  }

  const commitRename = async () => {
    if (operation.current) return
    operation.current = true
    setBusy(true)
    try {
      await props.onRename(props.scene.id, name)
      setRenaming(false)
    } catch (error) {
      setName(props.scene.name)
      toast.error(error instanceof Error ? error.message : '重命名失败')
    } finally { operation.current = false; setBusy(false) }
  }

  const remove = async () => {
    const removed = await props.onRemove(props.scene.id)
    if (removed) {
      toast('结构已删除', {
        action: { label: '撤销', onClick: () => { void props.onRestore(removed).catch((error) => toast.error(error.message)) } },
      })
    }
  }

  return (
    <div
      ref={sortable.setNodeRef}
      style={style}
      className={cn(
        'group flex min-h-12 items-center border-t border-ink/10 bg-frost px-1.5',
        props.selected && 'bg-white/70',
        sortable.isDragging && 'z-10 bg-white shadow-lg',
      )}
    >
      <button
        type="button"
        aria-label={props.selected ? '取消选择结构' : '选择结构'}
        onClick={() => props.onToggleSelect(props.scene.id)}
        disabled={props.disabled}
        className={cn('flex h-9 w-7 items-center justify-center text-ink/35 hover:text-ink disabled:opacity-35',
          props.selected && 'text-ink')}
      >
        {props.selected ? <CheckSquare2 size={14} /> : <Square size={14} />}
      </button>
      <button
        type="button"
        aria-label="拖动排序"
        className="flex h-9 w-7 cursor-grab items-center justify-center text-ink/30"
        {...sortable.attributes}
        {...sortable.listeners}
      >
        <GripVertical size={14} />
      </button>
      {renaming ? (
        <input
          autoFocus
          value={name}
          maxLength={40}
          onChange={(event) => setName(event.target.value)}
          onBlur={commitRename}
          onKeyDown={(event) => {
            if (event.key === 'Enter') commitRename()
            if (event.key === 'Escape') {
              setName(props.scene.name)
              setRenaming(false)
            }
          }}
          className="h-8 min-w-0 flex-1 border border-ink/20 bg-white px-2 text-xs outline-none"
        />
      ) : (
        <button
          type="button"
          disabled={props.disabled}
          onClick={() => props.onLoad(props.scene)}
          className="min-w-0 flex-1 px-1 text-left disabled:opacity-40"
        >
          <span className="block truncate text-xs font-medium text-ink">{props.scene.name}</span>
          <span className="font-mono text-[10px] text-ink/40">{props.scene.blocks.length} 方块</span>
        </button>
      )}
      <RowAction disabled={busy || props.disabled} label="载入结构" icon={FolderOpen} onClick={() => props.onLoad(props.scene)} />
      <RowAction disabled={busy || props.disabled} label="覆盖保存" icon={Save} onClick={async () => { await props.onUpdate(props.scene.id, props.currentBlocks); toast.success('结构已覆盖保存到服务器') }} />
      <RowAction disabled={busy || props.disabled} label="重命名" icon={Pencil} onClick={() => setRenaming(true)} />
      <RowAction disabled={busy || props.disabled} label="导出结构" icon={Download} onClick={() => downloadServerFile(`scenes/export?sample_id=${props.scene.id}`, `${props.scene.name}.json`)} />
      <RowAction disabled={busy || props.disabled} label="删除结构" icon={Trash2} onClick={remove} danger />
    </div>
  )
}

function RowAction({
  label,
  icon: Icon,
  onClick,
  danger,
  disabled,
}: {
  label: string
  icon: typeof Save
  onClick: () => void | Promise<void>
  danger?: boolean
  disabled?: boolean
}) {
  const [busy, setBusy] = useState(false)
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled || busy}
      onClick={async () => {
        if (busy) return
        setBusy(true)
        try { await onClick() } catch (error) { toast.error((error as Error).message) }
        finally { setBusy(false) }
      }}
      className={cn(
        'hidden h-8 w-7 items-center justify-center text-ink/45 hover:bg-white group-hover:flex focus:flex',
        danger && 'hover:text-signal',
      )}
    >
      <Icon size={13} />
    </button>
  )
}


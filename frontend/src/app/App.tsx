import { AnimatePresence, motion } from 'framer-motion'
import { Cloud, CloudOff, RefreshCw, Search, Tags, Sparkles } from 'lucide-react'
import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react'
import { Quaternion, Vector3 } from 'three'
import { Toaster, toast } from 'sonner'

import { CommandPalette } from '@/components/command'
import { InspectorPanel } from '@/components/inspector'
import { MobilePanels } from '@/components/mobile'
import { SceneManager } from '@/components/scenes'
import { EventTimeline } from '@/components/timeline'
import { BlockPalette, SimulationControls } from '@/components/toolbar'
import { useSceneLibrary, useSimulation } from '@/hooks'
import {
  BLOCK_BY_KIND,
  cn,
  facingTowardPlayer,
  swipeFacing,
  type Swipe,
} from '@/lib'
import type {
  BlockSpec,
  EditorTool,
  EngineCommand,
  PlacedBlock,
  Position,
  WorldBlockInput,
} from '@/types'

interface HistoryEntry {
  undo: EngineCommand
  redo: EngineCommand
}

const WorldCanvas = lazy(() =>
  import('@/components/world').then((module) => ({ default: module.WorldCanvas })),
)

export function App() {
  const simulation = useSimulation()
  const library = useSceneLibrary()
  const [tool, setTool] = useState<EditorTool>('slime_block')
  const [facing, setFacing] = useState<BlockSpec['facing']>('positive_z')
  const [autoFacing, setAutoFacing] = useState(true)
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null)
  const [running, setRunning] = useState(false)
  const [speed, setSpeed] = useState(4)
  const [checkpointReady, setCheckpointReady] = useState(false)
  const [undoStack, setUndoStack] = useState<HistoryEntry[]>([])
  const [redoStack, setRedoStack] = useState<HistoryEntry[]>([])

  const snapshot = simulation.snapshot
  const applySimulation = simulation.apply
  const selectedBlock = useMemo(
    () =>
      snapshot?.blocks.find(
        (block) =>
          selectedPosition &&
          block.position.x === selectedPosition.x &&
          block.position.y === selectedPosition.y &&
          block.position.z === selectedPosition.z,
      ) ?? null,
    [selectedPosition, snapshot?.blocks],
  )
  const currentBlocks = useMemo<WorldBlockInput[]>(
    () =>
      snapshot?.blocks.map((block) => ({
        position: block.position,
        block: { kind: block.kind, facing: block.facing },
      })) ?? [],
    [snapshot?.blocks],
  )
  const editingDisabled = !snapshot
  const structureDisabled =
    running || simulation.isApplying || !!snapshot?.motions.length || !snapshot

  const executeEdit = useCallback(
    async (redo: EngineCommand, undo: EngineCommand) => {
      if (editingDisabled) return false
      const result = await simulation.apply(redo)
      if (!result) return false
      if (!running) {
        setUndoStack((items) => [...items.slice(-99), { redo, undo }])
        setRedoStack([])
        setCheckpointReady(false)
      }
      return true
    },
    [editingDisabled, running, simulation],
  )

  const setBlockAt = useCallback(
    async (position: Position, cameraObject?: { position: { x: number; y: number; z: number } }) => {
      if (!snapshot || tool === 'inspect' || tool === 'erase') return
      if (structureDisabled) {
        toast.error('结构正在运动，暂时不能放置方块；先复位或等待动作结束')
        return
      }
      const previous = snapshot.blocks.find((block) => samePosition(block.position, position))
      const directional = tool !== 'slime_block' && tool !== 'honey_block' && tool !== 'glass'
        && tool !== 'redstone_block' && BLOCK_BY_KIND[tool]?.directional !== false
      const player = cameraObject?.position
      const placedFacing = autoFacing && directional && player
        ? facingTowardPlayer(position, new Vector3(player.x, player.y, player.z))
        : facing
      const redo: EngineCommand = {
        type: 'set_block',
        position,
        block: { kind: tool, facing: placedFacing },
      }
      const undo: EngineCommand = previous
        ? {
            type: 'set_block',
            position,
            block: { kind: previous.kind, facing: previous.facing },
          }
        : { type: 'remove_block', position }
      if (await executeEdit(redo, undo)) setSelectedPosition(position)
    },
    [autoFacing, executeEdit, facing, snapshot, tool],
  )

  const removeBlock = useCallback(
    async (block: PlacedBlock) => {
      const redo: EngineCommand = { type: 'remove_block', position: block.position }
      const undo: EngineCommand = {
        type: 'set_block',
        position: block.position,
        block: { kind: block.kind, facing: block.facing },
      }
      if (await executeEdit(redo, undo)) setSelectedPosition(null)
    },
    [executeEdit],
  )

  const rotateBlock = useCallback(
    (block: PlacedBlock, swipe: Swipe, event: { camera: { quaternion: Quaternion } }) => {
      if (structureDisabled) {
        toast.error('结构正在运动，暂时不能旋转方块；先复位或等待动作结束')
        return
      }
      const next = swipeFacing(block.facing, swipe, event.camera.quaternion)
      if (next === block.facing) return
      void executeEdit(
        { type: 'set_block', position: block.position, block: { kind: block.kind, facing: next } },
        { type: 'set_block', position: block.position, block: { kind: block.kind, facing: block.facing } },
      )
      setSelectedPosition(block.position)
    },
    [executeEdit, structureDisabled],
  )

  const handleBlockAction = useCallback(
    (block: PlacedBlock, adjacent: Position, camera?: { position: { x: number; y: number; z: number } }) => {
      if (tool === 'inspect') setSelectedPosition(block.position)
      else if (tool === 'erase') void removeBlock(block)
      else void setBlockAt(adjacent, camera)
    },
    [removeBlock, setBlockAt, tool],
  )

  const handleGroundAction = useCallback(
    (position: Position, camera?: { position: { x: number; y: number; z: number } }) => {
      if (tool === 'inspect') setSelectedPosition(null)
      else if (tool !== 'erase') void setBlockAt(position, camera)
    },
    [setBlockAt, tool],
  )

  const updateSelected = useCallback(
    (spec: BlockSpec) => {
      if (!selectedBlock) return
      void executeEdit(
        { type: 'set_block', position: selectedBlock.position, block: spec },
        {
          type: 'set_block',
          position: selectedBlock.position,
          block: { kind: selectedBlock.kind, facing: selectedBlock.facing },
        },
      )
    },
    [executeEdit, selectedBlock],
  )

  const undo = useCallback(async () => {
    const entry = undoStack.at(-1)
    if (!entry || editingDisabled) return
    if (await simulation.apply(entry.undo)) {
      setUndoStack((items) => items.slice(0, -1))
      setRedoStack((items) => [...items, entry])
      setCheckpointReady(false)
    }
  }, [editingDisabled, simulation, undoStack])

  const redo = useCallback(async () => {
    const entry = redoStack.at(-1)
    if (!entry || editingDisabled) return
    if (await simulation.apply(entry.redo)) {
      setRedoStack((items) => items.slice(0, -1))
      setUndoStack((items) => [...items, entry])
      setCheckpointReady(false)
    }
  }, [editingDisabled, redoStack, simulation])

  const ensureCheckpoint = useCallback(async () => {
    if (checkpointReady) return true
    const result = await simulation.apply({ type: 'create_checkpoint' })
    if (!result) return false
    setCheckpointReady(true)
    return true
  }, [checkpointReady, simulation])

  const stepOnce = useCallback(async () => {
    if (running || !(await ensureCheckpoint())) return
    await simulation.apply({ type: 'step', ticks: 1 })
  }, [ensureCheckpoint, running, simulation])

  const toggleRunning = useCallback(async () => {
    if (running) {
      setRunning(false)
      return
    }
    if (await ensureCheckpoint()) setRunning(true)
  }, [ensureCheckpoint, running])

  useEffect(() => {
    if (!running) return
    let cancelled = false
    let timer: number | undefined
    let appliedTicks = 0
    const startedAt = performance.now()

    const pump = async () => {
      if (cancelled) return
      const elapsed = performance.now() - startedAt
      const targetTicks = Math.floor((elapsed * speed) / 1000)
      const dueTicks = Math.min(1000, targetTicks - appliedTicks)
      if (dueTicks > 0) {
        const result = await applySimulation({ type: 'step', ticks: dueTicks })
        if (!result) {
          if (!cancelled) setRunning(false)
          return
        }
        appliedTicks += dueTicks
      }
      if (!cancelled) timer = window.setTimeout(() => void pump(), 10)
    }

    timer = window.setTimeout(() => void pump(), 10)
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [applySimulation, running, speed])

  const reset = useCallback(async () => {
    setRunning(false)
    const result = await simulation.apply({ type: 'restore_checkpoint' })
    if (result) setSelectedPosition(null)
  }, [simulation])

  const replaceWorld = useCallback(
    async (blocks: WorldBlockInput[]) => {
      const redo: EngineCommand = { type: 'replace_world', blocks }
      const undoCommand: EngineCommand = { type: 'replace_world', blocks: currentBlocks }
      if (await executeEdit(redo, undoCommand)) {
        setSelectedPosition(null)
        setRunning(false)
      }
    },
    [currentBlocks, executeEdit],
  )

  const clearWorld = useCallback(() => {
    if (!snapshot || snapshot.blocks.length === 0 || running) return
    void replaceWorld([])
  }, [replaceWorld, running, snapshot])

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.matches('input, textarea, [contenteditable="true"]')) return
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        void (event.shiftKey ? redo() : undo())
      } else if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'y') {
        event.preventDefault()
        void redo()
      } else if (event.key === 'Delete' && selectedBlock) {
        void removeBlock(selectedBlock)
      } else if (event.code === 'Space') {
        event.preventDefault()
        void toggleRunning()
      }
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [redo, removeBlock, selectedBlock, toggleRunning, undo])

  if (!snapshot) {
    return (
      <div className="flex h-dvh items-center justify-center bg-frost text-ink">
        <AnimatePresence mode="wait">
          <motion.div
            key={simulation.connectionState}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center"
          >
            {simulation.connectionState === 'error' ? (
              <>
                <CloudOff size={24} />
                <p className="mt-3 text-sm">模拟服务连接失败</p>
                <button
                  type="button"
                  onClick={simulation.reconnect}
                  className="mt-4 flex h-10 items-center border border-ink/20 bg-white px-4 text-sm"
                >
                  <RefreshCw size={15} className="mr-2" />重新连接
                </button>
              </>
            ) : (
              <>
                <div className="h-1 w-32 overflow-hidden bg-bench">
                  <motion.div
                    className="h-full w-1/2 bg-signal"
                    animate={{ x: ['-100%', '200%'] }}
                    transition={{ repeat: Infinity, duration: 1.1, ease: 'linear' }}
                  />
                </div>
                <p className="mt-3 text-sm text-ink/55">正在建立模拟会话</p>
              </>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    )
  }

  const palette = (
    <BlockPalette
      selected={tool}
      facing={facing}
      autoFacing={autoFacing}
      disabled={editingDisabled}
      onSelect={setTool}
      onFacingChange={setFacing}
      onAutoFacingChange={setAutoFacing}
      compact
    />
  )
  const inspector = (
    <InspectorPanel
      block={selectedBlock}
      disabled={editingDisabled}
      onUpdate={updateSelected}
      onDelete={() => selectedBlock && void removeBlock(selectedBlock)}
    />
  )
  const sceneManagerProps = {
    scenes: library.scenes,
    currentBlocks,
    disabled: structureDisabled || library.loading || !!library.error,
    loading: library.loading,
    error: library.error ?? library.saveError,
    onReload: library.discardAndReload,
    onImport: library.importFile,
    onCreate: library.create,
    onUpdate: library.update,
    onRename: library.rename,
    onRemove: library.remove,
    onRemoveMany: library.removeMany,
    onRestore: library.restore,
    onReorder: library.reorder,
    onLoad: (scene: (typeof library.scenes)[number]) => void replaceWorld(scene.blocks),
  }

  return (
    <div className="grid h-dvh w-full min-w-0 max-w-full grid-cols-[minmax(0,1fr)] grid-rows-[52px_minmax(0,1fr)_124px] overflow-hidden bg-frost text-ink md:grid-rows-[56px_minmax(0,1fr)_144px]">
      <header className="flex min-w-0 items-center border-b border-ink/15 bg-frost px-2 md:px-4">
        <div className="mr-1 shrink-0 md:mr-6">
          <div className="flex items-baseline gap-2">
            <h1 className="font-mono text-xs font-bold sm:text-sm">MCSCAI</h1>
            <span className="hidden text-xs text-ink/50 xl:inline">基岩版航械调试台</span>
          </div>
        </div>
        <SimulationControls
          tick={snapshot.tick}
          running={running}
          busy={simulation.isApplying}
          speed={speed}
          canReset={checkpointReady}
          canUndo={undoStack.length > 0}
          canRedo={redoStack.length > 0}
          onToggleRunning={() => void toggleRunning()}
          onStep={() => void stepOnce()}
          onReset={() => void reset()}
          onClear={clearWorld}
          onUndo={() => void undo()}
          onRedo={() => void redo()}
          onSpeedChange={setSpeed}
        />
        <div className="ml-auto flex shrink-0 items-center gap-1 pl-1 sm:gap-2 sm:pl-2">
          <a href="#search" aria-label="搜索与训练" title="搜索与训练" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-ink/15 bg-white/45 text-ink/65 sm:h-9 sm:w-9"><Search size={17} /></a>
          <a href="#generate" aria-label="AI 移动线生成" title="AI 移动线生成" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-ink/15 bg-white/45 text-ink/65 sm:h-9 sm:w-9"><Sparkles size={17} /></a>
          <a href="#labeler" aria-label="移动线打标器" title="移动线打标器" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-ink/15 bg-white/45 text-ink/65 sm:h-9 sm:w-9"><Tags size={17} /></a>
          <ConnectionState state={simulation.connectionState} />
          <CommandPalette
            running={running}
            onToggleRunning={() => void toggleRunning()}
            onStep={() => void stepOnce()}
            onReset={() => void reset()}
            onClear={clearWorld}
            onInspect={() => setTool('inspect')}
            onErase={() => setTool('erase')}
          />
        </div>
      </header>

      <main className="grid h-full w-full min-h-0 min-w-0 max-w-full grid-cols-1 overflow-hidden lg:grid-cols-[220px_minmax(0,1fr)_280px]">
        <aside className="hidden min-h-0 flex-col border-r border-ink/15 bg-frost lg:flex">
          <div className="p-3">
            <h2 className="mb-2.5 text-[11px] font-semibold text-ink/55">方块工具</h2>
            <BlockPalette
              selected={tool}
              facing={facing}
              autoFacing={autoFacing}
              disabled={editingDisabled}
              onSelect={setTool}
              onFacingChange={setFacing}
              onAutoFacingChange={setAutoFacing}
            />
          </div>
          <SceneManager {...sceneManagerProps} />
        </aside>

        <section className="relative h-full w-full min-h-0 min-w-0 max-w-full overflow-hidden bg-bench">
          <Suspense fallback={<div className="h-full w-full animate-pulse bg-bench" />}>
            <WorldCanvas
              snapshot={snapshot}
              selectedPosition={selectedPosition}
              disabled={editingDisabled}
              onSelect={(block) => setSelectedPosition(block?.position ?? null)}
              onBlockAction={handleBlockAction}
              onGroundAction={handleGroundAction}
            onBlockSwipe={rotateBlock}
              onErase={(block) => void removeBlock(block)}
            />
          </Suspense>
          <div className="pointer-events-none absolute left-3 top-3 border border-ink/15 bg-frost/85 px-2 py-1 font-mono text-[10px] text-ink/55 backdrop-blur">
            {snapshot.blocks.length} 方块 · {snapshot.motions.length} 运动组
          </div>
          <MobilePanels
            palette={palette}
            inspector={inspector}
            scenes={<SceneManager {...sceneManagerProps} />}
          />
        </section>

        <aside className="hidden min-h-0 border-l border-ink/15 bg-frost lg:block">
          {inspector}
        </aside>
      </main>

      <EventTimeline
        tick={snapshot.tick}
        events={snapshot.events}
        onSelectPosition={setSelectedPosition}
      />
      <Toaster position="top-center" richColors closeButton />
    </div>
  )
}

function samePosition(left: Position, right: Position) {
  return left.x === right.x && left.y === right.y && left.z === right.z
}

function ConnectionState({ state }: { state: string }) {
  const connected = state === 'connected'
  return (
    <div
      className={cn(
        'hidden h-9 items-center border px-2 text-[11px] sm:flex',
        connected
          ? 'border-ink/15 bg-white/45 text-ink/55'
          : 'border-signal/30 bg-signal/5 text-signal',
      )}
    >
      {connected ? <Cloud size={14} /> : <CloudOff size={14} />}
      <span className="ml-1.5 hidden xl:inline">{connected ? '引擎在线' : '连接中断'}</span>
    </div>
  )
}

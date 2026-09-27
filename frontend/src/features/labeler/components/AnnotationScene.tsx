import { Suspense, useMemo, useRef, useState, type ReactNode } from 'react'
import { Play } from 'lucide-react'
import type { Camera } from 'three'
import { BoxOutline, WorldCanvas } from '@/components/world'
import type { Direction, SimulationSnapshot } from '@/types'
import type { LabelSample, MarkTool, NormalizedStructure, TargetPoint } from '../types'
import { COMPACT_TOOL_CLASS, TARGET_LOAD_BLOCKS } from '../constants'
import { ForwardIndicator } from './ForwardIndicator'
import { AnnotationCameraBridge } from './AnnotationCameraBridge'
import { TargetLoads } from './TargetLoads'
import { AnnotationToolbar } from './AnnotationToolbar'
import { annotationError, columnRear } from '../utils'
import { useLabelReplay } from '../hooks/useLabelReplay'
import { useViewportScale } from '../hooks/useViewportScale'
import { ReplayToolbar } from './ReplayToolbar'
import { ReplayTargets } from './ReplayTargets'

export function AnnotationScene({
  sample,
  shape,
  onMark,
  onForward,
  tool,
  onTool,
  mobileActions,
  compute,
  maxTicks,
  calculationBusy,
  focus,
  onResetFocus,
}: {
  sample: LabelSample
  shape: NormalizedStructure
  onMark: (x: number, y: number, z?: number) => void
  onForward: (direction: Direction) => Promise<void>
  tool: MarkTool
  onTool: (tool: MarkTool) => void
  mobileActions: ReactNode
  compute: (id: string, maxTicks: number) => Promise<LabelSample>
  maxTicks: number
  calculationBusy: boolean
  focus: TargetPoint | null
  onResetFocus: () => void
}) {
  const [selected, setSelected] = useState<number | null>(null)
  const [slice, setSlice] = useState(-2)
  const [cameraVersion, setCameraVersion] = useState(0)
  const [showFullLoad, setShowFullLoad] = useState(true)
  const cameraRef = useRef<Camera | null>(null)
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const viewportScale = useViewportScale(viewportRef)
  const replay = useLabelReplay(sample, maxTicks, compute)
  const snapshot = useMemo<SimulationSnapshot>(
    () => ({
      tick: 0,
      arms: [],
      motions: [],
      events: [],
      blocks: shape.blocks.flatMap((block, index) =>
        block.kind && block.layer === 0 && block.position.z <= slice
          ? [
              {
                id: index + 1,
                kind: block.kind,
                facing: block.facing,
                position: block.position,
                powered: false,
                strongly_powered: false,
                piston_phase: null,
                observer_phase: null,
              },
            ]
          : [],
      ),
    }),
    [shape, slice],
  )
  const frontZ = Math.max(-2, ...sample.targets.map((point) => (point.z ?? 0) + (showFullLoad ? TARGET_LOAD_BLOCKS - 1 : 0)))
  const view = useMemo(
    () => ({
      target: focus ? [focus.x, focus.y, focus.z - 2] as [number, number, number] : [
        (shape.width - 1) / 2,
        (shape.height - 1) / 2,
        (frontZ - shape.depth - 1) / 2,
      ] as [number, number, number],
      distance: viewportScale * (focus ? 7 : Math.max(
        5,
        Math.max(shape.width, shape.height, shape.depth + frontZ + 2) * 1.3,
      )),
    }),
    [shape.width, shape.height, shape.depth, frontZ, focus, viewportScale],
  )
  const renderedSnapshot = useMemo(() => {
    if (!replay.frame || !replay.info) return snapshot
    if (showFullLoad) return replay.frame.snapshot
    const hidden = new Set(replay.info.targets.flatMap(target => target.blockIds.slice(1)))
    return { ...replay.frame.snapshot, blocks: replay.frame.snapshot.blocks.filter(block => !hidden.has(block.id)) }
  }, [replay.frame, replay.info, showFullLoad, snapshot])
  const resetCamera = () => { onResetFocus(); setCameraVersion(value => value + 1) }
  const selectedBlock = selected === null ? null : shape.blocks[selected]
  return (
    <section
      className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-bench"
      aria-label="移动线三维预览"
    >
      <div ref={viewportRef} className="relative min-h-0 flex-1 overflow-hidden">
      <Suspense
        fallback={
          <div className="flex h-full animate-pulse items-center justify-center text-sm text-ink/60">
            正在载入三维贴图…
          </div>
        }
      >
        <WorldCanvas
          key={cameraVersion}
          snapshot={renderedSnapshot}
          selectedPosition={replay.active ? null : selectedBlock?.position ?? null}
          disabled={replay.active}
          view={view}
          showGround={false}
          onSelect={(block) => setSelected(block ? block.id - 1 : null)}
          onBlockAction={(block) => {
            setSelected(block.id - 1)
            onMark(block.position.x, block.position.y, block.position.z)
          }}
          onGroundAction={() => undefined}
          onErase={() => undefined}
        >
          {!replay.active && shape.blocks.map((block, index) =>
            (!block.kind || block.layer !== 0) && block.position.z <= slice ? (
              <mesh
                key={index}
                position={[
                  block.position.x,
                  block.position.y,
                  block.position.z,
                ]}
                onClick={(event) => {
                  event.stopPropagation()
                  if (event.delta < 5) {
                    setSelected(index)
                    onMark(block.position.x, block.position.y, block.position.z)
                  }
                }}
              >
                <boxGeometry
                  args={
                    block.layer === 0 ? [0.94, 0.94, 0.94] : [1.01, 1.01, 1.01]
                  }
                />
                <meshStandardMaterial
                  color="#c79e68"
                  wireframe={block.layer !== 0}
                />
                <BoxOutline
                  color={selected === index ? '#c84c4c' : '#775a34'}
                />
              </mesh>
            ) : null,
          )}
          {replay.frame && replay.info ? <ReplayTargets info={replay.info} snapshot={replay.frame.snapshot} /> : <TargetLoads sample={sample} showFullLoad={showFullLoad} />}
          {!replay.active && sample.pushPoint && (
            <group
              position={[
                sample.pushPoint.x,
                sample.pushPoint.y,
                (sample.pushPoint.z ?? columnRear(shape, sample.pushPoint) ?? -shape.depth - 1) - 1,
              ]}
            >
              <mesh>
                <boxGeometry args={[0.8, 0.8, 0.8]} />
                <meshBasicMaterial color="#c84c4c" wireframe />
              </mesh>
            </group>
          )}
          <ForwardIndicator shape={shape} />
          <AnnotationCameraBridge cameraRef={cameraRef} />
        </WorldCanvas>
      </Suspense>
      </div>
      {replay.active ? <ReplayToolbar replay={replay} showFullLoad={showFullLoad} onLoadToggle={() => setShowFullLoad(value => !value)} onResetCamera={resetCamera} mobileActions={mobileActions} /> : <AnnotationToolbar forward={sample.forward} onForward={onForward} cameraRef={cameraRef}
        tool={tool} onTool={onTool} showFullLoad={showFullLoad} onLoadToggle={() => setShowFullLoad((value) => !value)}
        slice={slice} depth={shape.depth} onSlice={setSlice} onReset={resetCamera}
        runControl={<button className={`${COMPACT_TOOL_CLASS} border-sky-400 bg-sky-100`} aria-label="运行移动线" title="运行移动线" disabled={calculationBusy || !!annotationError(sample) || sample.blocks.some(block => !block.kind || block.layer !== 0)} onClick={() => void replay.start()}><Play size={16} /></button>}
        mobileActions={mobileActions} />}
    </section>
  )
}

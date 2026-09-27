import { OrbitControls } from '@react-three/drei'
import { Canvas, type ThreeEvent } from '@react-three/fiber'
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type ElementRef,
  type ReactNode,
} from 'react'
import {
  ACESFilmicToneMapping,
  MOUSE,
  PCFSoftShadowMap,
  Quaternion,
  SRGBColorSpace,
  TOUCH,
  Vector3,
  WebGLRenderer,
} from 'three'

import type { PlacedBlock, Position, SimulationSnapshot } from '@/types'

import { BlockMesh } from './BlockMesh'
import { PistonArmMesh } from './PistonArmMesh'
import { motionPosition, samePosition } from './utils'
import { useTapGesture, type SwipeDirection } from './useTapGesture'

const ORBIT_MOUSE_BUTTONS = {
  LEFT: MOUSE.PAN,
  MIDDLE: MOUSE.DOLLY,
  RIGHT: MOUSE.ROTATE,
}
const ORBIT_TOUCHES = {
  ONE: TOUCH.ROTATE,
  TWO: TOUCH.DOLLY_PAN,
}

type OrbitControlsHandle = ElementRef<typeof OrbitControls>

interface CameraSnapshot {
  position: Vector3
  quaternion: Quaternion
  target: Vector3
  zoom: number
}

interface WorldCanvasProps {
  children?: ReactNode
  view?: { target: [number, number, number]; distance: number; position?: [number, number, number] }
  showGround?: boolean
  snapshot: SimulationSnapshot
  selectedPosition: Position | null
  disabled: boolean
  onSelect: (block: PlacedBlock | null) => void
  onBlockAction: (block: PlacedBlock, adjacent: Position, camera: ThreeEvent<PointerEvent>['camera']) => void
  onGroundAction: (position: Position, camera: ThreeEvent<PointerEvent>['camera']) => void
  onBlockSwipe?: (block: PlacedBlock, direction: SwipeDirection, event: ThreeEvent<PointerEvent>) => void
  onErase: (block: PlacedBlock) => void
  /** 场景内拖动（例如拖网格边缘改尺寸）时锁住相机，不改动轨道控制的开关。 */
  lockControls?: boolean
}

async function createRenderer({ canvas }: { canvas: HTMLCanvasElement }) {
  const gpu = (navigator as Navigator & { gpu?: { requestAdapter: () => Promise<unknown> } }).gpu
  if (gpu && await gpu.requestAdapter().catch(() => null)) {
    const { WebGPURenderer } = await import('three/webgpu')
    const renderer = new WebGPURenderer({ canvas, antialias: true })
    await renderer.init()
    renderer.outputColorSpace = SRGBColorSpace
    renderer.toneMapping = ACESFilmicToneMapping
    return renderer
  }
  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: false })
  renderer.outputColorSpace = SRGBColorSpace
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = PCFSoftShadowMap
  return renderer
}

export function WorldCanvas({
  snapshot,
  selectedPosition,
  disabled,
  onSelect,
  onBlockAction,
  onGroundAction,
  onBlockSwipe,
  onErase,
  children,
  view,
  showGround = true,
  lockControls = false,
}: WorldCanvasProps) {
  const controlsRef = useRef<OrbitControlsHandle>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const cameraSnapshot = useRef<CameraSnapshot | null>(null)

  const syncCameraState = useCallback(() => {
    const controls = controlsRef.current
    const container = containerRef.current
    if (!controls || !container) return
    const camera = controls.object
    const values = [
      ...camera.position.toArray(),
      ...camera.quaternion.toArray(),
      camera.zoom,
      ...controls.target.toArray(),
    ].map((value) => Number(value.toFixed(6)))
    container.dataset.cameraState = JSON.stringify(values)
  }, [])

  const captureView = useCallback(() => {
    const controls = controlsRef.current
    if (!controls) return
    cameraSnapshot.current = {
      position: controls.object.position.clone(),
      quaternion: controls.object.quaternion.clone(),
      target: controls.target.clone(),
      zoom: controls.object.zoom,
    }
  }, [])

  const restoreView = useCallback(() => {
    const controls = controlsRef.current
    const saved = cameraSnapshot.current
    if (!controls || !saved) return
    controls.object.position.copy(saved.position)
    controls.object.quaternion.copy(saved.quaternion)
    controls.object.zoom = saved.zoom
    controls.object.updateProjectionMatrix()
    controls.target.copy(saved.target)
    controls.update()
    syncCameraState()
  }, [syncCameraState])

  useEffect(() => {
    const controls = controlsRef.current
    if (!controls) return
    controls.target.set(...(view?.target ?? [0, 1, 0] as [number, number, number]))
    if (view) controls.object.position.set(...(view.position ?? [view.target[0] + view.distance, view.target[1] + view.distance * 0.8, view.target[2] + view.distance] as [number, number, number]))
    controls.update()
    syncCameraState()
  }, [syncCameraState, view])

  const gesture = useTapGesture(disabled, captureView, restoreView)
  // 只切换单指旋转：双指缩放与平移必须始终可用，否则铺满屏幕时无法调整视角。
  const setControlsRotate = useCallback((enabled: boolean) => {
    const controls = controlsRef.current
    if (controls) controls.enableRotate = enabled
  }, [])
  useEffect(() => {
    const controls = controlsRef.current
    if (!controls || !lockControls) return
    // 拖动期间只把相机状态按住：不改 enablePan/enableRotate，
    // 避免双指手势中途切换开关导致视角瞬移。
    captureView()
    const hold = () => {
      const saved = cameraSnapshot.current
      if (!saved) return
      controls.object.position.copy(saved.position)
      controls.object.quaternion.copy(saved.quaternion)
      controls.object.zoom = saved.zoom
      controls.object.updateProjectionMatrix()
      controls.target.copy(saved.target)
      syncCameraState()
    }
    controls.addEventListener('change', hold)
    return () => controls.removeEventListener('change', hold)
  }, [captureView, lockControls, syncCameraState])
  useEffect(() => {
    const container = containerRef.current
    const controls = controlsRef.current
    if (!container || !controls) return
    // 双指期间只保留缩放：禁掉旋转与平移，捏合就不会把视角带跑。
    // 只在“第二指落下”和“全部抬起”这两个时刻切换，避免手势中途改状态造成跳变。
    let multi = false
    const start = (event: TouchEvent) => {
      if (multi || event.touches.length < 2) return
      multi = true
      controls.enableRotate = false
      controls.enablePan = false
    }
    const end = (event: TouchEvent) => {
      if (!multi || event.touches.length >= 2) return
      multi = false
      controls.enableRotate = true
      controls.enablePan = true
    }
    container.addEventListener('touchstart', start, { passive: true })
    container.addEventListener('touchend', end, { passive: true })
    container.addEventListener('touchcancel', end, { passive: true })
    return () => {
      container.removeEventListener('touchstart', start)
      container.removeEventListener('touchend', end)
      container.removeEventListener('touchcancel', end)
    }
  }, [])
  // 方块上的手势期间关闭轨道控制，避免滑动旋转时视角同时被拖动后又回弹。
  const meshGesture = useMemo(() => ({
    begin: (event: ThreeEvent<PointerEvent>, action: () => void, swipeAction?: Parameters<typeof gesture.begin>[2]) => {
      // 只有左键手势才冻结视角；右键用于旋转视角，不能拦。
      if (event.button === 0) setControlsRotate(false)
      gesture.begin(event, action, swipeAction)
    },
    move: gesture.move,
    end: (event: ThreeEvent<PointerEvent>) => { gesture.end(event); setControlsRotate(true) },
    cancel: (event: ThreeEvent<PointerEvent>) => { gesture.cancel(event); setControlsRotate(true) },
    cancelAll: () => { gesture.cancelAll(); setControlsRotate(true) },
  }), [gesture, setControlsRotate])
  useEffect(() => {
    // 指针在画布外抬起时也要恢复视角控制，避免冻结状态残留。
    const release = () => setControlsRotate(true)
    window.addEventListener('pointerup', release)
    window.addEventListener('pointercancel', release)
    window.addEventListener('blur', release)
    return () => {
      window.removeEventListener('pointerup', release)
      window.removeEventListener('pointercancel', release)
      window.removeEventListener('blur', release)
    }
  }, [setControlsRotate])

  const handleGround = useCallback(
    (event: ThreeEvent<PointerEvent>) => {
      if (disabled || event.button !== 0) return
      const position = {
        x: Math.round(event.point.x),
        y: 0,
        z: Math.round(event.point.z),
      }
      gesture.begin(event, () => onGroundAction(position, event.camera))
    },
    [disabled, gesture, onGroundAction],
  )

  return (
    <div ref={containerRef} className="h-full w-full min-w-0 max-w-full overflow-hidden">
      <Canvas
        className="h-full w-full"
        shadows
        dpr={[1, 1.75]}
        camera={{ position: view ? view.position ?? [view.target[0] + view.distance, view.target[1] + view.distance * 0.8, view.target[2] + view.distance] : [9, 8, 11], fov: 42, near: 0.1, far: 1000 }}
        gl={createRenderer as never}
        onPointerMissed={() => onSelect(null)}
      >
      <color attach="background" args={['#DCE9EC']} />
      {!view && <fog attach="fog" args={['#DCE9EC', 28, 70]} />}
      <ambientLight intensity={1.25} />
      <directionalLight
        castShadow
        position={[9, 14, 7]}
        intensity={2.1}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />
      <Suspense fallback={null}>
        {snapshot.blocks.map((block) => (
          <BlockMesh
            key={block.id}
            block={block}
            renderPosition={motionPosition(block, snapshot.tick, snapshot.motions)}
            selected={samePosition(selectedPosition, block.position)}
            disabled={disabled}
            gesture={meshGesture}
            onSelect={onSelect}
            onFaceAction={onBlockAction}
            onErase={onErase}
            onSwipe={onBlockSwipe ?? (() => undefined)}
          />
        ))}
        {snapshot.arms.map((arm) => (
          <PistonArmMesh key={arm.piston_id} arm={arm} tick={snapshot.tick} />
        ))}
        {children}
      </Suspense>
      {showGround && <gridHelper args={[40, 40, '#6E9EAC', '#B7CDD3']} position={[0, -0.51, 0]} />}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.5, 0]}
        visible={showGround}
        onPointerDown={handleGround}
        onPointerMove={gesture.move}
        onPointerUp={gesture.end}
        onPointerCancel={gesture.cancel}
      >
        <planeGeometry args={[40, 40]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
        <OrbitControls
          ref={controlsRef}
          target={view?.target}
          makeDefault
          enableDamping={false}
          minDistance={3}
          maxDistance={view ? Math.max(55, view.distance * 5) : 55}
          maxPolarAngle={Math.PI * 0.92}
          mouseButtons={ORBIT_MOUSE_BUTTONS}
          touches={ORBIT_TOUCHES}
          onChange={syncCameraState}
          onEnd={syncCameraState}
        />
      </Canvas>
    </div>
  )
}

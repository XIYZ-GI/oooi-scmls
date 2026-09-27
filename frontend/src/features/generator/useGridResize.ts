import { useCallback, useEffect, useRef } from 'react'
import type { ThreeEvent } from '@react-three/fiber'
import { useThree } from '@react-three/fiber'
import { Plane, Raycaster, Vector2, Vector3 } from 'three'
import { GRID_LIMIT, clamp } from './taskEdit'

export type ResizeAxis = 'width' | 'height'

/**
 * 拖动网格边缘调整宽高。网格外围一圈都可以起拖，按落点离哪条边最近决定方向；
 * 位移按“屏幕像素 × 起始时每像素对应的世界距离”换算，拖动时即使视角移动也不会失控。
 */
export function useGridResize({ enabled, onResize, onDragChange }: {
  enabled: boolean
  onResize: (changes: { width?: number; height?: number }, anchor: 'start' | 'end') => void
  onDragChange?: (active: boolean) => void
}) {
  const { camera, gl } = useThree()
  const raycaster = useRef(new Raycaster())
  const plane = useRef(new Plane(new Vector3(0, 0, 1), 0))
  const handlers = useRef({ onResize, onDragChange })
  handlers.current = { onResize, onDragChange }
  // 记录当前按下的指针，用于识别双指缩放：多指手势一律不触发尺寸拖拽。
  const pressed = useRef(new Set<number>())
  useEffect(() => {
    const add = (event: PointerEvent) => pressed.current.add(event.pointerId)
    const remove = (event: PointerEvent) => pressed.current.delete(event.pointerId)
    window.addEventListener('pointerdown', add, true)
    window.addEventListener('pointerup', remove, true)
    window.addEventListener('pointercancel', remove, true)
    return () => {
      window.removeEventListener('pointerdown', add, true)
      window.removeEventListener('pointerup', remove, true)
      window.removeEventListener('pointercancel', remove, true)
    }
  }, [])

  /** 屏幕坐标 → 网格平面上的世界坐标。 */
  const project = useCallback((clientX: number, clientY: number) => {
    const rect = gl.domElement.getBoundingClientRect()
    const point = new Vector3()
    const ndc = new Vector2(((clientX - rect.left) / rect.width) * 2 - 1,
                            -((clientY - rect.top) / rect.height) * 2 + 1)
    raycaster.current.setFromCamera(ndc, camera)
    return raycaster.current.ray.intersectPlane(plane.current, point) ? point : null
  }, [camera, gl])

  const drag = useCallback((axis: ResizeAxis, sign: 1 | -1, base: number, clientX: number, clientY: number, pointerId: number) => {
    const origin = project(clientX, clientY)
    if (!origin) return
    const shifted = axis === 'width' ? project(clientX + 1, clientY) : project(clientX, clientY - 1)
    const perPixel = shifted ? (axis === 'width' ? shifted.x - origin.x : shifted.y - origin.y) : 0
    if (!perPixel) return
    const move = (event: PointerEvent) => {
      const delta = sign * (axis === 'width' ? event.clientX - clientX : clientY - event.clientY)
      const value = clamp(base + Math.round(delta * perPixel), GRID_LIMIT.min, GRID_LIMIT.max)
      handlers.current.onResize(axis === 'width' ? { width: value } : { height: value },
                                sign === -1 ? 'start' : 'end')
    }
    const startId = pointerId
    const stop = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
      window.removeEventListener('pointerdown', guard)
      handlers.current.onDragChange?.(false)
    }
    // 第二根手指按下说明是缩放/平移手势：撤销本次拖拽，把尺寸还原到起始值。
    const guard = (event: PointerEvent) => {
      if (event.pointerId === startId || pressed.current.size < 2) return
      stop()
      handlers.current.onResize(axis === 'width' ? { width: base } : { height: base },
                                sign === -1 ? 'start' : 'end')
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
    window.addEventListener('pointerdown', guard)
    handlers.current.onDragChange?.(true)
  }, [project])

  /** 在外围起拖时判断方向；点在网格内部返回 false，交给目标点标注。 */
  return useCallback((size: { width: number; height: number; offset?: { x: number; y: number } }) => (event: ThreeEvent<PointerEvent>) => {
    if (!enabled) return
    // 双指及以上手势留给视角操作，不做尺寸拖拽。
    if (pressed.current.size > 1) return
    // 判定面位于相机一侧，真实位置用网格平面（z=0）的投影结果，避免两套坐标混用。
    const point = project(event.nativeEvent.clientX, event.nativeEvent.clientY)
    if (!point) return
    // 绘制原点在左/下边拖动后会移动，判定要换算回设计坐标。
    const x = point.x + (size.offset?.x ?? 0)
    const y = point.y + (size.offset?.y ?? 0)
    const options = [
      { axis: 'width' as ResizeAxis, sign: 1 as const, base: size.width, overshoot: x - (size.width - 0.5) },
      { axis: 'width' as ResizeAxis, sign: -1 as const, base: size.width, overshoot: -0.5 - x },
      { axis: 'height' as ResizeAxis, sign: 1 as const, base: size.height, overshoot: y - (size.height - 0.5) },
      { axis: 'height' as ResizeAxis, sign: -1 as const, base: size.height, overshoot: -0.5 - y },
    ]
    const best = options.reduce((left, right) => (right.overshoot > left.overshoot ? right : left))
    // 只在网格外半格内起拖：太远的地方不响应，避免误触。
    if (best.overshoot <= 0 || best.overshoot > 0.5) return
    event.stopPropagation()
    drag(best.axis, best.sign, best.base, event.nativeEvent.clientX, event.nativeEvent.clientY, event.nativeEvent.pointerId)
  }, [drag, enabled, project])
}

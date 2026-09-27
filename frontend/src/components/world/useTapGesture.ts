import type { ThreeEvent } from '@react-three/fiber'
import { useCallback, useEffect, useRef } from 'react'

interface PointerCandidate {
  x: number
  y: number
  lastX: number
  lastY: number
  pointerType: string
  startedAt: number
  target: Element | null
  action: () => void
  swipeAction?: SwipeHandler
}

const MAX_TOUCH_TAP_MS = 500
const SWIPE_TOUCH_PX = 24
const SWIPE_MOUSE_PX = 14
const STALE_POINTER_MS = 12000

export type SwipeDirection = 'left' | 'right' | 'up' | 'down'
export type SwipeHandler = (direction: SwipeDirection, event: ThreeEvent<PointerEvent>) => void

export interface TapGesture {
  begin: (event: ThreeEvent<PointerEvent>, action: () => void, swipeAction?: SwipeHandler) => void
  move: (event: ThreeEvent<PointerEvent>) => void
  end: (event: ThreeEvent<PointerEvent>) => void
  cancel: (event: ThreeEvent<PointerEvent>) => void
  cancelAll: () => void
}

export function useTapGesture(
  disabled: boolean,
  captureView: () => void,
  restoreView: () => void,
  onSwipe?: SwipeHandler,
): TapGesture {
  const active = useRef(new Map<number, PointerCandidate>())
  const gestureCancelled = useRef(false)

  const begin = useCallback(
    (event: ThreeEvent<PointerEvent>, action: () => void, swipeAction?: SwipeHandler) => {
      event.stopPropagation()
      if (disabled || event.button !== 0) return
      // 上一次触摸若没有收到抬指事件，会留下过期候选并让后续手势全部失效。
      active.current.delete(event.pointerId)
      const now = performance.now()
      for (const [id, candidate] of active.current) {
        if (now-candidate.startedAt > STALE_POINTER_MS) {
          active.current.delete(id)
        }
      }
      if (active.current.size === 0) gestureCancelled.current = false
      if (active.current.size === 0) captureView()
      const target =
        event.nativeEvent.target instanceof Element ? event.nativeEvent.target : null
      try {
        target?.setPointerCapture(event.pointerId)
      } catch {
        // 某些移动浏览器不允许三维画布捕获合成触控指针，后续清理仍然有效。
      }
      active.current.set(event.pointerId, {
        x: event.nativeEvent.clientX,
        y: event.nativeEvent.clientY,
        lastX: event.nativeEvent.clientX,
        lastY: event.nativeEvent.clientY,
        pointerType: event.pointerType,
        startedAt: performance.now(),
        target,
        action,
        swipeAction,
      })
      if (active.current.size > 1) gestureCancelled.current = true
    },
    [captureView, disabled],
  )

  const move = useCallback((event: ThreeEvent<PointerEvent>) => {
    const candidate = active.current.get(event.pointerId)
    if (!candidate) return
    candidate.lastX = event.nativeEvent.clientX
    candidate.lastY = event.nativeEvent.clientY
    const distance = Math.hypot(
      event.nativeEvent.clientX - candidate.x,
      event.nativeEvent.clientY - candidate.y,
    )
    const threshold = candidate.pointerType === 'touch' ? 10 : 5
    if (distance > threshold) gestureCancelled.current = true
  }, [])

  const end = useCallback((event: ThreeEvent<PointerEvent>) => {
    event.stopPropagation()
    const candidate = active.current.get(event.pointerId)
    const heldTooLong =
      candidate?.pointerType === 'touch' &&
      performance.now() - candidate.startedAt > MAX_TOUCH_TAP_MS
    const shouldRun =
      !!candidate &&
      active.current.size === 1 &&
      !gestureCancelled.current &&
      !heldTooLong
    try {
      candidate?.target?.releasePointerCapture(event.pointerId)
    } catch {
      // 指针可能已被浏览器释放。
    }
    active.current.delete(event.pointerId)
    if (active.current.size === 0) gestureCancelled.current = false

    const swipe = candidate?.swipeAction ?? onSwipe
    if (swipe && candidate && active.current.size === 0) {
      const dx = candidate.lastX-candidate.x
      const dy = candidate.lastY-candidate.y
      const needed = candidate.pointerType === 'touch' ? SWIPE_TOUCH_PX : SWIPE_MOUSE_PX
      if (Math.hypot(dx, dy) >= needed) {
        const direction: SwipeDirection = Math.abs(dx) >= Math.abs(dy)
          ? (dx < 0 ? 'left' : 'right')
          : (dy < 0 ? 'up' : 'down')
        restoreView()
        window.requestAnimationFrame(() => swipe(direction, event))
        return
      }
    }

    if (shouldRun) {
      restoreView()
      // 先让视角控制完成触控收尾，再提交世界变更，避免重渲染干扰相机。
      window.requestAnimationFrame(() => candidate.action())
    }
  }, [onSwipe, restoreView])

  const cancel = useCallback((event: ThreeEvent<PointerEvent>) => {
    const candidate = active.current.get(event.pointerId)
    try {
      candidate?.target?.releasePointerCapture(event.pointerId)
    } catch {
      // 指针可能已被浏览器释放。
    }
    active.current.delete(event.pointerId)
    gestureCancelled.current = true
    if (active.current.size === 0) gestureCancelled.current = false
  }, [])

  const cancelAll = useCallback(() => {
    for (const [pointerId, candidate] of active.current) {
      try {
        candidate.target?.releasePointerCapture(pointerId)
      } catch {
        // 指针可能已被浏览器释放。
      }
    }
    active.current.clear()
    gestureCancelled.current = false
  }, [])

  useEffect(() => {
    // 浏览器或系统手势可能吞掉 pointerup/pointercancel，这里在窗口层兜底清理。
    const release = (event: PointerEvent) => {
      const candidate = active.current.get(event.pointerId)
      if (!candidate) return
      try {
        candidate.target?.releasePointerCapture(event.pointerId)
      } catch {
        // 指针可能已经被浏览器释放。
      }
      active.current.delete(event.pointerId)
      if (active.current.size === 0) gestureCancelled.current = false
    }
    const clear = () => {
      active.current.clear()
      gestureCancelled.current = false
    }
    window.addEventListener('pointerup', release)
    window.addEventListener('pointercancel', release)
    window.addEventListener('blur', clear)
    document.addEventListener('visibilitychange', clear)
    return () => {
      window.removeEventListener('pointerup', release)
      window.removeEventListener('pointercancel', release)
      window.removeEventListener('blur', clear)
      document.removeEventListener('visibilitychange', clear)
    }
  }, [])

  return { begin, move, end, cancel, cancelAll }
}

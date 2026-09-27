import { useEffect, useRef, useState } from 'react'
import type { LabelSample } from '../types'
import { annotationError } from '../utils'
import { LOAD_TIMING_PROTOCOL } from '../constants'

export function useAutomaticTiming(sample: LabelSample | null, compute: (id: string, maxTicks: number) => Promise<LabelSample>) {
  const [enabled, setEnabled] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [maxTicks, setMaxTicks] = useState(200)
  const [state, setState] = useState<{ phase: 'idle' | 'waiting' | 'running' | 'error'; message: string }>({ phase: 'idle', message: '' })
  const latest = useRef({ sample, compute })
  latest.current = { sample, compute }
  useEffect(() => {
    setMaxTicks(latest.current.sample?.timing?.maxTicks ?? 200)
  }, [sample?.id])
  const consumedAttempt = useRef(0)
  const blocked = sample?.blocks.some((block) => !block.kind || block.layer !== 0)
    ? '样本包含模拟器不支持的方块或附加层；点标注和原始文件已保存在服务器。' : ''
  const inputKey = sample && !annotationError(sample) && !blocked
    ? JSON.stringify([sample.id, sample.blocks, sample.forward, sample.pushPoint, sample.targets, LOAD_TIMING_PROTOCOL]) : null

  useEffect(() => {
    let disposed = false
    const force = attempt !== consumedAttempt.current
    if (!enabled || !inputKey || (latest.current.sample?.timing && !force)) {
      setState({ phase: 'idle', message: '' })
      return
    }
    setState({ phase: 'waiting', message: '正在保存点标注，准备计算时序…' })
    const timer = window.setTimeout(async () => {
      consumedAttempt.current = attempt
      const selected = latest.current.sample
      if (!selected) return
      setState({ phase: 'running', message: '服务器模拟器正在计算时序…' })
      try {
        await latest.current.compute(selected.id, maxTicks)
        if (!disposed) setState({ phase: 'idle', message: '' })
      } catch (error) {
        if (!disposed) setState({ phase: 'error', message: error instanceof Error ? error.message : '时序计算失败，请重试' })
      }
    }, 800)
    return () => { disposed = true; window.clearTimeout(timer) }
  }, [enabled, inputKey, attempt, maxTicks])

  return { ...state, blocked, enabled, setEnabled, maxTicks,
    setMaxTicks: (value: number) => { setMaxTicks(value); setAttempt((current) => current + 1) },
    retry: () => setAttempt((current) => current + 1),
  }
}

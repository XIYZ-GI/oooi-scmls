import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { libraryRequest } from '@/lib/serverLibrary'
import type { SimulationSnapshot } from '@/types'
import type { LabelSample, TimingResult, TimingTarget } from '../types'

export interface LabelReplayInfo {
  id: string
  frameCount: number
  chunkSize: number
  result: TimingResult
  targets: Array<TimingTarget & { blockIds: number[] }>
}

export interface LabelReplayFrame { snapshot: SimulationSnapshot; targets: TimingTarget[] }
interface Chunk { start: number; frames: LabelReplayFrame[] }

export function useLabelReplay(sample: LabelSample, maxTicks: number, compute: (id: string, maxTicks: number) => Promise<LabelSample>) {
  const [info, setInfo] = useState<LabelReplayInfo | null>(null)
  const [frame, setFrame] = useState<LabelReplayFrame | null>(null)
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(false)
  const [speed, setSpeed] = useState(5)
  const serial = useRef(0)
  const lock = useRef(false)
  const cache = useRef(new Map<number, Chunk>())
  const requestAbort = useRef<AbortController | null>(null)
  const inputKey = JSON.stringify([sample.id, sample.blocks, sample.forward, sample.pushPoint, sample.targets, maxTicks])
  const invalidate = useCallback(() => {
    ++serial.current
    requestAbort.current?.abort()
  }, [])
  const clear = useCallback(() => {
    invalidate(); lock.current = false; cache.current.clear()
    setInfo(null); setFrame(null); setIndex(0); setPlaying(false); setLoading(false); setActive(false)
  }, [invalidate])
  useEffect(() => {
    clear()
    return invalidate
  }, [inputKey, clear, invalidate])

  const read = async (value: LabelReplayInfo, at: number, version: number, signal?: AbortSignal) => {
    const chunk = Math.floor(at / value.chunkSize)
    let data = cache.current.get(chunk)
    if (!data) {
      data = await libraryRequest<Chunk>(`samples/${sample.id}/replays/${value.id}/chunks/${chunk}`, { signal })
      if (version !== serial.current) return null
      cache.current.set(chunk, data)
      if (cache.current.size > 4) cache.current.delete(cache.current.keys().next().value!)
    }
    return data.frames[at - data.start]
  }
  const seek = async (at: number) => {
    if (!info) return
    setPlaying(false)
    const target = Math.max(0, Math.min(info.frameCount - 1, at))
    const version = ++serial.current
    requestAbort.current?.abort()
    const controller = new AbortController()
    requestAbort.current = controller
    setLoading(true)
    try {
      const next = await read(info, target, version, controller.signal)
      if (version !== serial.current || !next) return
      setIndex(target); setFrame(next)
    } catch (error) {
      if (version === serial.current) toast.error((error as Error).message)
    } finally { if (version === serial.current) setLoading(false) }
  }

  useEffect(() => {
    if (!playing || !info || loading) return
    if (index >= info.frameCount - 1) { setPlaying(false); return }
    const version = serial.current
    let disposed = false
    const timer = window.setTimeout(async () => {
      try {
        const next = await read(info, index + 1, version)
        if (disposed || serial.current !== version || !next) return
        setFrame(next); setIndex(index + 1)
      } catch (error) {
        if (!disposed && serial.current === version) { setPlaying(false); toast.error((error as Error).message) }
      }
    }, 1000 / speed)
    return () => { disposed = true; window.clearTimeout(timer) }
    // read使用当前样本及有界缓存，轨迹更换由inputKey清理。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, info, index, speed, loading])

  const start = async () => {
    if (lock.current) return
    if (info) {
      if (index === info.frameCount - 1) await seek(0)
      setPlaying(value => !value)
      return
    }
    lock.current = true; setActive(true); setLoading(true)
    const version = ++serial.current
    try {
      const current = sample.timing?.replay && sample.timing.maxTicks === maxTicks ? sample : await compute(sample.id, maxTicks)
      if (serial.current !== version) return
      const id = current.timing?.replay?.id
      if (!id) throw new Error('服务器没有返回运行轨迹，请重试')
      const value = await libraryRequest<LabelReplayInfo>(`samples/${sample.id}/replays/${id}`)
      if (serial.current !== version) return
      const first = await read(value, 0, version)
      if (serial.current !== version || !first) return
      setInfo(value); setFrame(first); setIndex(0); setPlaying(true)
      toast.success('运行轨迹已载入')
    } catch (error) {
      if (serial.current === version) { setActive(false); toast.error((error as Error).message) }
    } finally {
      if (serial.current === version) { lock.current = false; setLoading(false) }
    }
  }
  return { info, frame, index, playing, loading, active, speed, setSpeed, start, seek, clear,
    pause: () => setPlaying(false) }
}

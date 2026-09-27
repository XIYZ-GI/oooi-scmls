import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { request } from './api'
import type { Replay } from './types'

export function useReplay(jobId: string | undefined, candidate: number) {
  const [replay, setReplay] = useState<Replay | null>(null)
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const serial = useRef(0)
  const inFlight = useRef(false)
  useEffect(() => {
    ++serial.current; inFlight.current = false
    setReplay(null); setIndex(0); setPlaying(false); setLoading(false)
    return () => { ++serial.current }
  }, [jobId, candidate])
  const advance = (current: number, value: Replay) => {
    let next = Math.min(current+1, value.trace.length-1)
    while (next+1 < value.trace.length && value.trace[next+1].snapshot.tick === value.trace[next].snapshot.tick) next++
    return next
  }
  useEffect(() => {
    if (!playing || !replay) return
    const timer = setInterval(() => setIndex(current => {
      if (current >= replay.trace.length-1) { setPlaying(false); return current }
      return advance(current, replay)
    }), 140)
    return () => clearInterval(timer)
  }, [playing, replay])
  const start = async (run: boolean) => {
    if (!jobId || inFlight.current) return
    if (replay) {
      if (run) { if (index >= replay.trace.length-1) setIndex(0); setPlaying(!playing) }
      else { setPlaying(false); setIndex(i => advance(i, replay)) }
      return
    }
    const version = serial.current
    inFlight.current = true; setLoading(true)
    try {
      const result = await request<Replay>(`/jobs/${jobId}/candidates/${candidate}/replay`)
      if (serial.current !== version) return
      if (!result.trace?.length) throw new Error(result.reason || '该候选未进入模拟，无法回放')
      setReplay(result); setIndex(0); setPlaying(run)
    } catch (e) { if (serial.current === version) toast.error((e as Error).message) }
    finally { if (serial.current === version) { inFlight.current = false; setLoading(false) } }
  }
  const clear = () => { ++serial.current; inFlight.current = false; setReplay(null); setIndex(0); setPlaying(false); setLoading(false) }
  return { replay, index, playing, loading, start, clear, pause: () => setPlaying(false),
    reset: () => { setPlaying(false); setIndex(0) }, seek: (i: number) => { setPlaying(false); setIndex(i) } }
}

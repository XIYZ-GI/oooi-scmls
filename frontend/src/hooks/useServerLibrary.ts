import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { libraryRequest, type LibraryKind, type ServerDocument } from '@/lib/serverLibrary'
import { migrateLegacyLibrary } from '@/lib/legacyMigration'

export function useServerLibrary<T extends ServerDocument>(kind: LibraryKind) {
  const [items, setItems] = useState<T[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<'saved' | 'pending' | 'error'>('saved')
  const [saveError, setSaveError] = useState<string | null>(null)
  const current = useRef<T[]>([])
  const revisions = useRef(new Map<string, number>())
  const pending = useRef(new Map<string, Partial<T>>())
  const flight = useRef<Promise<boolean> | null>(null)
  const mounted = useRef(true)
  const generation = useRef(0)

  const publish = useCallback((values: T[]) => {
    generation.current += 1
    current.current = values
    if (mounted.current) setItems(values)
  }, [])

  const accept = useCallback((value: T) => {
    if (value.revision < (revisions.current.get(value.id) ?? 0)) return
    revisions.current.set(value.id, value.revision)
    const patch = pending.current.get(value.id)
    const invalidTiming = kind === 'samples' && patch && ['forward', 'pushPoint', 'targets'].some((key) => key in patch)
    const merged = { ...value, ...patch, ...(invalidTiming ? { timing: null } : {}) }
    publish(current.current.some((item) => item.id === value.id) ? current.current.map((item) => item.id === value.id ? merged : item) : [...current.current, merged])
  }, [kind, publish])

  const reload = useCallback(async (showLoading = true) => {
    if (pending.current.size || flight.current) return
    if (showLoading) setLoading(true)
    const started = generation.current
    try {
      const values = await libraryRequest<T[]>(kind)
      if (!pending.current.size && !flight.current && started === generation.current) {
        values.forEach((item) => revisions.current.set(item.id, item.revision))
        publish(values)
      }
      setError(null)
    } catch (cause) {
      if (showLoading) setError(cause instanceof Error ? cause.message : '读取服务器失败')
    } finally { if (showLoading) setLoading(false) }
  }, [kind, publish])

  const initialize = useCallback(async () => {
    setLoading(true)
    try {
      const count = await migrateLegacyLibrary(kind)
      if (count) toast.success(`已将 ${count} 个旧版${kind === 'samples' ? '标注样本' : '结构'}迁移到服务器`)
      await reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '旧数据上传失败，浏览器副本仍保留')
      setLoading(false)
    }
  }, [kind, reload])

  useEffect(() => {
    mounted.current = true
    void initialize()
    const interval = window.setInterval(() => void reload(false), 10000)
    const focus = () => void reload(false)
    window.addEventListener('focus', focus)
    return () => { mounted.current = false; window.clearInterval(interval); window.removeEventListener('focus', focus) }
  }, [initialize, reload])

  const flush = useCallback((): Promise<boolean> => {
    if (flight.current) return flight.current
    const run = async () => {
      while (pending.current.size) {
        const [id, changes] = pending.current.entries().next().value!
        pending.current.delete(id)
        try {
          const saved = await libraryRequest<T>(`${kind}/${id}`, { method: 'PATCH', body: JSON.stringify({ revision: revisions.current.get(id), changes }) })
          accept(saved)
        } catch (cause) {
          pending.current.set(id, { ...changes, ...pending.current.get(id) })
          const message = cause instanceof Error ? cause.message : '保存到服务器失败'
          if (mounted.current) { setSaveState('error'); setSaveError(message) }
          toast.error(message)
          return false
        }
      }
      if (mounted.current) { setSaveState('saved'); setSaveError(null) }
      return true
    }
    const task = run().finally(() => { flight.current = null })
    flight.current = task
    return task
  }, [accept, kind])

  const update = useCallback((id: string, changes: Partial<T>) => {
    if (!current.current.some((item) => item.id === id)) return
    pending.current.set(id, { ...pending.current.get(id), ...changes })
    const invalidTiming = kind === 'samples' && ['forward', 'pushPoint', 'targets'].some((key) => key in changes)
    publish(current.current.map((item) => item.id === id ? { ...item, ...changes, ...(invalidTiming ? { timing: null } : {}) } : item))
    setSaveState('pending')
    setSaveError(null)
  }, [kind, publish])

  useEffect(() => {
    if (saveState !== 'pending') return
    const timer = window.setTimeout(() => void flush(), 400)
    return () => window.clearTimeout(timer)
  }, [items, saveState, flush])

  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => {
      if (pending.current.size || flight.current) { event.preventDefault(); event.returnValue = '' }
    }
    window.addEventListener('beforeunload', leave)
    return () => { window.removeEventListener('beforeunload', leave); void flush() }
  }, [flush])

  const discardAndReload = useCallback(async () => {
    if (flight.current) await flight.current
    pending.current.clear()
    setSaveState('saved')
    setSaveError(null)
    await reload()
  }, [reload])

  const remove = useCallback(async (id: string) => {
    if (!(await flush())) return null
    const item = current.current.find((value) => value.id === id)
    if (!item) return null
    await libraryRequest(`${kind}/${id}?revision=${revisions.current.get(id)}`, { method: 'DELETE' })
    publish(current.current.filter((value) => value.id !== id))
    return item
  }, [flush, kind, publish])

  const removeMany = useCallback(async (ids: string[]) => {
    if (!ids.length) return []
    if (!(await flush())) return []
    const removed: T[] = []
    for (const id of ids) {
      const item = current.current.find((value) => value.id === id)
      if (!item) continue
      await libraryRequest(`${kind}/${id}?revision=${revisions.current.get(id)}`, { method: 'DELETE' })
      removed.push(item)
    }
    if (removed.length) {
      const removedIds = new Set(removed.map((item) => item.id))
      publish(current.current.filter((value) => !removedIds.has(value.id)))
    }
    return removed
  }, [flush, kind, publish])

  const restore = useCallback(async (id: string) => {
    const value = await libraryRequest<T>(`${kind}/${id}/restore`, { method: 'POST' })
    accept(value)
  }, [accept, kind])

  return { items, loading, error, saveState, saveError, current, revisions, reload: initialize, refresh: reload, flush, update, accept, remove, removeMany, restore, discardAndReload, publish }
}

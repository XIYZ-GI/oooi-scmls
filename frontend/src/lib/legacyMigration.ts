import { libraryRequest, type LibraryKind } from './serverLibrary'

const migrations = new Map<LibraryKind, Promise<number>>()

async function readLegacySamples(): Promise<{ items: Record<string, unknown>[]; clear: () => Promise<void> }> {
  const db = await new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open('mcscai-labeler-v1', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('samples', { keyPath: 'id' })
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(new Error('无法读取旧版浏览器数据，迁移尚未完成'))
  })
  const items = await new Promise<Record<string, unknown>[]>((resolve, reject) => {
    const request = db.transaction('samples').objectStore('samples').getAll()
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(new Error('读取旧标注失败'))
  })
  return { items, clear: async () => {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction('samples', 'readwrite')
      for (const item of items) {
        const store = transaction.objectStore('samples')
        const request = store.get(String(item.id))
        request.onsuccess = () => { if (JSON.stringify(request.result) === JSON.stringify(item)) store.delete(String(item.id)) }
      }
      transaction.oncomplete = () => { db.close(); resolve() }
      transaction.onabort = () => { db.close(); reject(new Error('数据已上传，但旧浏览器副本清理失败')) }
    })
  } }
}

export function migrateLegacyLibrary(kind: LibraryKind): Promise<number> {
  const existing = migrations.get(kind)
  if (existing) return existing
  const task = (async () => {
    const sceneText = kind === 'scenes' ? localStorage.getItem('mcscai-scenes-v1') : null
    const legacy = kind === 'samples' ? await readLegacySamples() : {
      items: sceneText ? JSON.parse(sceneText) as Record<string, unknown>[] : [],
      clear: async () => { if (localStorage.getItem('mcscai-scenes-v1') === sceneText) localStorage.removeItem('mcscai-scenes-v1') },
    }
    if (!Array.isArray(legacy.items)) throw new Error('旧版结构数据损坏，未删除浏览器副本')
    if (legacy.items.length) await libraryRequest(`${kind}/migrate`, { method: 'POST', body: JSON.stringify({ items: legacy.items }) })
    await legacy.clear()
    return legacy.items.length
  })()
  migrations.set(kind, task)
  task.catch(() => migrations.delete(kind))
  return task
}

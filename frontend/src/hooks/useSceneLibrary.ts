import { libraryRequest } from '@/lib/serverLibrary'
import type { WorldBlockInput } from '@/types'
import { useServerLibrary } from './useServerLibrary'

export interface StoredScene {
  id: string
  revision: number
  name: string
  blocks: WorldBlockInput[]
  updatedAt: string
}

export function useSceneLibrary() {
  const library = useServerLibrary<StoredScene>('scenes')
  const create = async (name: string, blocks: WorldBlockInput[]) => {
    const scene = await libraryRequest<StoredScene>('scenes', { method: 'POST', body: JSON.stringify({ name: name.trim(), blocks }) })
    library.accept(scene)
    return scene
  }
  const save = async (id: string, changes: Partial<StoredScene>) => {
    library.update(id, changes)
    if (!(await library.flush())) throw new Error('服务器保存失败，请处理保存错误后重试')
  }
  const importFile = async (file: File) => {
    if (file.size > 64 * 1024 * 1024) throw new Error('结构文件不能超过 64 MiB')
    const scene = await libraryRequest<StoredScene>('scenes/import', { method: 'POST', body: file, headers: { 'Content-Type': 'application/json' } })
    library.accept(scene)
    return scene
  }
  const rename = async (id: string, name: string) => {
    const value = name.trim()
    if (!value) throw new Error('结构名称不能为空')
    if (library.current.current.some((scene) => scene.id !== id && scene.name === value)) throw new Error('结构名称已存在')
    await save(id, { name: value })
  }
  const reorder = async (activeId: string, overId: string) => {
    if (!(await library.flush())) return
    const items = [...library.current.current]
    const from = items.findIndex((scene) => scene.id === activeId)
    const to = items.findIndex((scene) => scene.id === overId)
    if (from < 0 || to < 0 || from === to) return
    const [scene] = items.splice(from, 1)
    items.splice(to, 0, scene)
    await libraryRequest('scenes/reorder', { method: 'POST', body: JSON.stringify({ ids: items.map((item) => item.id) }) })
    library.publish(items)
  }
  return { ...library, scenes: library.items, create, importFile, rename, reorder,
    update: (id: string, blocks: WorldBlockInput[]) => save(id, { blocks }),
    restore: (scene: StoredScene) => library.restore(scene.id),
  }
}

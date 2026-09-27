import { useCallback } from 'react'
import { toast } from 'sonner'
import { useServerLibrary } from '@/hooks/useServerLibrary'
import { libraryRequest } from '@/lib/serverLibrary'
import type { LabelSample } from '../types'

export function useLabelLibrary() {
  const library = useServerLibrary<LabelSample>('samples')
  const update = useCallback((id: string, changes: Partial<LabelSample>) => {
    const { timing: _timing, ...patch } = changes
    void _timing
    library.update(id, patch)
  }, [library.update])
  const rename = useCallback((id: string, name: string) => {
    const value = name.trim()
    if (!value || value.length > 120) throw new Error('名称不能为空，且不能超过 120 字符')
    if (library.current.current.some((sample) => sample.id !== id && sample.name === value)) throw new Error('样本名称已存在')
    update(id, { name: value })
  }, [library.current, update])
  const remove = useCallback(async (id: string) => {
    try {
      const item = await library.remove(id)
      if (item) toast.success(`已从服务器删除「${item.name}」`, { duration: 15000, action: { label: '撤销', onClick: () => { void library.restore(id).catch((error) => toast.error(error.message)) } } })
    } catch (error) { toast.error((error as Error).message) }
  }, [library.remove, library.restore])
  const compute = useCallback(async (id: string, maxTicks: number) => {
    if (!(await library.flush())) throw new Error('点标注尚未保存到服务器，请先处理保存错误')
    const sample = await libraryRequest<LabelSample>(`samples/${id}/timing`, { method: 'POST', body: JSON.stringify({ revision: library.revisions.current.get(id), max_ticks: maxTicks }) })
    library.accept(sample)
    return sample
  }, [library.flush, library.accept, library.revisions])
  return { ...library, samples: library.items, update, rename, remove, compute }
}

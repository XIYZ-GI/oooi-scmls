import { useAutoAnimate } from '@formkit/auto-animate/react'
import { Check, FileBox, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { cn } from '@/lib'
import type { LabelSample } from '../types'
import { FIELD_CLASS } from '../constants'
import { Choice } from './Choice'

export function SampleList({
  samples,
  selectedId,
  onSelect,
}: {
  samples: LabelSample[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('name')
  const [list] = useAutoAnimate()
  const filtered = useMemo(
    () =>
      samples
        .filter(
          (sample) =>
            `${sample.name} ${sample.fileName} ${sample.author}`
              .toLowerCase()
              .includes(search.toLowerCase()) &&
            (filter === 'all' || sample.completed === (filter === 'done')),
        )
        .sort((a, b) =>
          sort === 'name'
            ? a.name.localeCompare(b.name, 'zh-CN', { numeric: true })
            : b.updatedAt.localeCompare(a.updatedAt),
        ),
    [samples, search, filter, sort],
  )
  return (
    <div className="space-y-3 p-3">
      <div className="flex items-center gap-2">
        <Search size={17} className="shrink-0 text-ink/50" />
        <input
          aria-label="搜索移动线"
          placeholder="搜索名称、来源"
          className={FIELD_CLASS}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Choice
          label="筛选标注状态"
          value={filter}
          options={[
            { value: 'all', label: '全部' },
            { value: 'todo', label: '待标注' },
            { value: 'done', label: '已完成' },
          ]}
          onChange={setFilter}
        />
        <Choice
          label="样本排序"
          value={sort}
          options={[
            { value: 'name', label: '名称排序' },
            { value: 'updated', label: '最近修改' },
          ]}
          onChange={setSort}
        />
      </div>
      <p className="text-xs text-ink/50">
        {samples.length} 个样本 ·{' '}
        {samples.filter((sample) => sample.completed).length} 个已完成
      </p>
      <div ref={list} className="space-y-1">
        {!filtered.length && (
          <p className="py-8 text-center text-sm text-ink/50">
            {samples.length
              ? '没有符合条件的样本'
              : '导入移动线后在这里选择样本'}
          </p>
        )}
        {filtered.map((sample) => (
          <button
            key={sample.id}
            className={cn(
              'flex min-h-16 w-full items-center gap-2 border px-3 py-2 text-left',
              selectedId === sample.id
                ? 'border-sky-400 bg-sky-100/60'
                : 'border-transparent hover:bg-white/60',
            )}
            aria-label={`选择样本 ${sample.name}`}
            aria-pressed={selectedId === sample.id}
            onClick={() => onSelect(sample.id)}
          >
            <FileBox size={18} className="shrink-0 text-sky-700" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">
                {sample.name}
              </span>
              <span className="text-[11px] text-ink/55">
                {sample.blocks.length} 方块 · {sample.targets.length} 目标
              </span>
            </span>
            {sample.completed && (
              <Check
                size={17}
                className="shrink-0 text-teal-700"
                aria-label="已完成"
              />
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

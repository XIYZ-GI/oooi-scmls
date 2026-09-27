/** 安卓离线模型选择与权重状态，交互与移动线生成网页保持一致。 */

import * as Dropdown from '@radix-ui/react-dropdown-menu'
import { Box, Check, ChevronDown, CircleAlert, LoaderCircle } from 'lucide-react'
import { cn } from '@/lib'
import type { ModelInfo } from './types'
import type { ModelState } from '@/bridge'

export function ModelCard({ model, models, onChange, state, message, disabled, parameters }: {
  model: ModelInfo | null
  models: ModelInfo[]
  onChange: (id: string) => void
  state: ModelState
  message: string
  disabled: boolean
  parameters?: number
}) {
  const count = model?.parameters ?? parameters ?? 0
  const size = count ? `${(count / 1_000_000).toFixed(1)}M 参数` : '参数量读取中'
  return <div className={cn('space-y-1.5', disabled && 'opacity-60')}>
    <h2 className="text-xs font-medium">模型</h2>
    <Dropdown.Root>
      <Dropdown.Trigger asChild disabled={disabled || !models.length}>
        <button type="button" aria-label="选择模型" className="group w-full rounded-md border border-ink/15 bg-white px-2 py-1.5 text-left outline-none transition-colors hover:border-sky-300 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-200 disabled:cursor-not-allowed">
          <span className="flex items-center gap-1.5">
            <Box size={14} className="shrink-0 text-ink/60" />
            <span className="min-w-0 flex-1 truncate text-xs font-medium">{model?.name ?? '正在读取模型清单'}</span>
            <ChevronDown size={14} className="shrink-0 text-ink/50 transition-transform group-data-[state=open]:rotate-180" />
          </span>
          <span className="mt-1 flex items-center gap-1.5 text-[11px] text-ink/55">
            {state === 'error' ? <><CircleAlert size={12} className="shrink-0 text-red-700" /><span className="truncate text-red-700">{message || '权重加载失败'}</span></>
              : state === 'loading' ? <><LoaderCircle size={12} className="shrink-0 animate-spin text-sky-600" /><span className="truncate">{message || '正在加载模型权重文件'}</span></>
              : <span>{size}</span>}
          </span>
        </button>
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content align="start" sideOffset={4} className="z-[70] w-[var(--radix-dropdown-menu-trigger-width)] max-w-[90vw] rounded-md border border-ink/15 bg-frost p-1 shadow-md">
          <Dropdown.RadioGroup value={model?.id ?? ''} onValueChange={onChange}>
            {models.map(row => <Dropdown.RadioItem key={row.id} value={row.id}
              className="relative cursor-pointer rounded px-7 py-2 text-xs outline-none data-[highlighted]:bg-sky-100">
              <Dropdown.ItemIndicator className="absolute left-2"><Check size={13} className="text-sky-700" /></Dropdown.ItemIndicator>
              <span className="flex items-center justify-between gap-3"><span className="truncate">{row.name}</span><span className="shrink-0 text-[11px] text-ink/50">{row.ready ? (row.parameters ? `${(row.parameters / 1_000_000).toFixed(1)}M` : '') : '加载中'}</span></span>
            </Dropdown.RadioItem>)}
          </Dropdown.RadioGroup>
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  </div>
}

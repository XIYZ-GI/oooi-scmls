import * as Dropdown from '@radix-ui/react-dropdown-menu'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib'
import { BUTTON } from './constants'
import type { ModelInfo } from './types'

export function ModelSelector({ models, selected, disabled, onChange }: {
  models: ModelInfo[]; selected: string; disabled: boolean; onChange: (id: string) => void
}) {
  const model = models.find(row => row.id === selected)
  return <div className="space-y-1.5">
    <h2 className="text-xs font-medium">模型</h2>
    <Dropdown.Root>
      <Dropdown.Trigger className={cn(BUTTON, 'w-full justify-between')} disabled={disabled}>
        <span className="truncate">{model?.name ?? '选择模型版本'}</span><ChevronDown size={14} className="shrink-0" />
      </Dropdown.Trigger>
      <Dropdown.Portal><Dropdown.Content align="start" sideOffset={4} className="z-[70] max-w-[90vw] rounded-md border border-ink/15 bg-frost p-1 shadow-md">
        <Dropdown.RadioGroup value={selected} onValueChange={onChange}>
          {models.map(row => <Dropdown.RadioItem key={row.id} value={row.id} disabled={!row.ready}
            className="relative cursor-pointer rounded px-7 py-2 text-xs outline-none data-[highlighted]:bg-sky-100 data-[disabled]:opacity-40">
            <Dropdown.ItemIndicator className="absolute left-2"><Check size={13} /></Dropdown.ItemIndicator>
            {row.name}{!row.ready ? ' · 不可用' : ''}
          </Dropdown.RadioItem>)}
        </Dropdown.RadioGroup>
      </Dropdown.Content></Dropdown.Portal>
    </Dropdown.Root>
  </div>
}

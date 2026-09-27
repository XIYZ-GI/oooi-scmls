import type { ReactNode } from 'react'
import { Drawer } from 'vaul'
import { X } from 'lucide-react'
import { COMPACT_TOOL_CLASS } from '../constants'

export function LabelDrawer({
  label,
  icon,
  children,
  compact = false,
}: {
  label: string
  icon: ReactNode
  children: ReactNode
  compact?: boolean
}) {
  return (
    <Drawer.Root>
      <Drawer.Trigger aria-label={label} className={compact ? COMPACT_TOOL_CLASS : 'flex min-h-11 items-center gap-2 rounded-md border border-ink/20 bg-white/95 px-4 text-sm shadow-sm'}>
        {icon}
        {!compact && label}
      </Drawer.Trigger>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-40 bg-ink/25" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col rounded-t-lg border-t border-ink/20 bg-frost outline-none">
          <div className="flex items-center justify-between border-b border-ink/10 px-4 py-2">
            <Drawer.Title className="text-sm font-semibold">
              {label}
            </Drawer.Title>
            <Drawer.Close
              className="flex h-10 w-10 items-center justify-center"
              aria-label="关闭面板"
            >
              <X size={18} />
            </Drawer.Close>
          </div>
          <Drawer.Description className="sr-only">
            查看移动线样本或编辑当前样本的推动点和目标点。
          </Drawer.Description>
          <div className="overflow-auto pb-6">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  )
}

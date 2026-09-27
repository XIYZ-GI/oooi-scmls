import { Drawer } from 'vaul'
import { Blocks, FolderOpen, SlidersHorizontal } from 'lucide-react'
import type { ReactNode } from 'react'

interface MobilePanelsProps {
  palette: ReactNode
  inspector: ReactNode
  scenes: ReactNode
}

export function MobilePanels({ palette, inspector, scenes }: MobilePanelsProps) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-4 z-20 flex justify-center gap-2 lg:hidden">
      <MobileDrawer label="方块工具" icon={Blocks}>
        {palette}
      </MobileDrawer>
      <MobileDrawer label="方块属性" icon={SlidersHorizontal}>
        {inspector}
      </MobileDrawer>
      <MobileDrawer label="服务器结构" icon={FolderOpen}>
        {scenes}
      </MobileDrawer>
    </div>
  )
}

function MobileDrawer({
  label,
  icon: Icon,
  children,
}: {
  label: string
  icon: typeof Blocks
  children: ReactNode
}) {
  return (
    <Drawer.Root>
      <Drawer.Trigger asChild>
        <button
          type="button"
          aria-label={label}
          className="pointer-events-auto flex h-12 w-12 items-center justify-center border border-ink/15 bg-white/90 text-ink shadow-lg backdrop-blur"
        >
          <Icon size={19} />
        </button>
      </Drawer.Trigger>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-40 bg-ink/25" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-50 max-h-[72dvh] border-t border-ink/15 bg-frost outline-none">
          <div className="mx-auto my-2 h-1 w-10 rounded-full bg-ink/20" />
          <Drawer.Title className="px-4 pb-3 text-sm font-semibold text-ink">{label}</Drawer.Title>
          <div className="max-h-[62dvh] overflow-auto px-4 pb-5">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  )
}

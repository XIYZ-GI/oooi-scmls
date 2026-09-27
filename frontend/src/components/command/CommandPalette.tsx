import { Command } from 'cmdk'
import {
  Eraser,
  MousePointer2,
  Pause,
  Play,
  RotateCcw,
  Search,
  StepForward,
  Trash2,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'

interface CommandPaletteProps {
  running: boolean
  onToggleRunning: () => void
  onStep: () => void
  onReset: () => void
  onClear: () => void
  onInspect: () => void
  onErase: () => void
}

export function CommandPalette(props: CommandPaletteProps) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((value) => !value)
      }
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])

  const run = (action: () => void) => {
    setOpen(false)
    action()
  }

  return (
    <>
      <button
        type="button"
        aria-label="打开快捷命令"
        onClick={() => setOpen(true)}
        className="hidden h-9 w-9 items-center justify-center border border-ink/15 bg-white/55 text-ink hover:bg-white sm:flex"
      >
        <Search size={16} />
      </button>
      <Command.Dialog
        open={open}
        onOpenChange={setOpen}
        label="快捷命令"
        className="fixed left-1/2 top-[18dvh] z-[70] w-[min(92vw,520px)] -translate-x-1/2 border border-ink/15 bg-white shadow-2xl outline-none"
      >
        <div className="flex items-center border-b border-ink/10 px-3">
          <Search size={17} className="text-ink/40" />
          <Command.Input
            autoFocus
            placeholder="搜索命令"
            className="h-12 min-w-0 flex-1 bg-transparent px-3 text-sm text-ink outline-none placeholder:text-ink/35"
          />
        </div>
        <Command.List className="max-h-80 overflow-y-auto p-2">
          <Command.Empty className="px-3 py-8 text-center text-sm text-ink/40">
            没有匹配命令
          </Command.Empty>
          <Command.Group heading="模拟" className="text-[10px] text-ink/40 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-2">
            <CommandItem
              icon={props.running ? Pause : Play}
              label={props.running ? '暂停模拟' : '运行模拟'}
              onSelect={() => run(props.onToggleRunning)}
            />
            <CommandItem icon={StepForward} label="推进一游戏刻" onSelect={() => run(props.onStep)} />
            <CommandItem icon={RotateCcw} label="恢复检查点" onSelect={() => run(props.onReset)} />
          </Command.Group>
          <Command.Group heading="编辑" className="mt-2 text-[10px] text-ink/40 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-2">
            <CommandItem icon={MousePointer2} label="切换到检查工具" onSelect={() => run(props.onInspect)} />
            <CommandItem icon={Eraser} label="切换到移除工具" onSelect={() => run(props.onErase)} />
            <CommandItem icon={Trash2} label="清空世界" onSelect={() => run(props.onClear)} />
          </Command.Group>
        </Command.List>
      </Command.Dialog>
      {open && <div className="fixed inset-0 z-[60] bg-ink/25" onClick={() => setOpen(false)} />}
    </>
  )
}

function CommandItem({
  icon: Icon,
  label,
  onSelect,
}: {
  icon: LucideIcon
  label: string
  onSelect: () => void
}) {
  return (
    <Command.Item
      value={label}
      onSelect={onSelect}
      className="flex h-10 cursor-default items-center px-2 text-sm text-ink outline-none data-[selected=true]:bg-frost"
    >
      <Icon size={16} className="mr-3 text-ink/55" />
      {label}
    </Command.Item>
  )
}


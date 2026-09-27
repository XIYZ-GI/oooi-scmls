import * as Tooltip from '@radix-ui/react-tooltip'
import { Crosshair, Eraser, MousePointer2 } from 'lucide-react'

import { BLOCKS, BLOCK_BY_KIND, DIRECTIONS, cn } from '@/lib'
import type { Direction, EditorTool } from '@/types'

interface BlockPaletteProps {
  selected: EditorTool
  facing: Direction
  autoFacing: boolean
  disabled?: boolean
  compact?: boolean
  onSelect: (tool: EditorTool) => void
  onFacingChange: (facing: Direction) => void
  onAutoFacingChange: (enabled: boolean) => void
}

export function BlockPalette({
  selected,
  facing,
  autoFacing,
  disabled = false,
  compact = false,
  onSelect,
  onFacingChange,
  onAutoFacingChange,
}: BlockPaletteProps) {
  const tools = [
    { id: 'inspect' as const, label: '检查', icon: MousePointer2 },
    { id: 'erase' as const, label: '移除', icon: Eraser },
  ]

  return (
    <Tooltip.Provider delayDuration={300}>
      <div className={cn('grid gap-1.5', compact ? 'grid-cols-6' : 'grid-cols-2')}>
        {tools.map(({ id, label, icon: Icon }) => (
          <Tooltip.Root key={id}>
            <Tooltip.Trigger asChild>
              <button
                type="button"
                disabled={disabled}
                aria-label={label}
                aria-pressed={selected === id}
                onClick={() => onSelect(id)}
                className={cn(
                  'flex h-11 min-w-11 items-center justify-center border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal disabled:opacity-40',
                  selected === id
                    ? 'border-ink bg-ink text-white'
                    : 'border-ink/15 bg-white/55 text-ink hover:bg-white',
                )}
              >
                <Icon size={18} strokeWidth={1.8} />
                {!compact && <span className="ml-2 text-xs font-medium">{label}</span>}
              </button>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content className="z-50 rounded-md bg-ink px-2 py-1 text-xs text-white">
                {label}
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        ))}
        {BLOCKS.map((block) => (
          <Tooltip.Root key={block.kind}>
            <Tooltip.Trigger asChild>
              <button
                type="button"
                disabled={disabled}
                aria-label={block.label}
                aria-pressed={selected === block.kind}
                onClick={() => onSelect(block.kind)}
                className={cn(
                  'flex h-12 min-w-11 items-center border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal disabled:opacity-40',
                  compact ? 'justify-center' : 'px-2',
                  selected === block.kind
                    ? 'border-ink bg-white shadow-[inset_3px_0_0_#C84C4C]'
                    : 'border-ink/15 bg-white/45 hover:bg-white',
                )}
              >
                <img
                  src={block.texture}
                  alt=""
                  className="h-7 w-7 [image-rendering:pixelated]"
                />
                {!compact && (
                  <span className="ml-2 min-w-0 break-all text-left text-[11px] font-medium leading-4 text-ink">
                    {block.label}
                  </span>
                )}
              </button>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content
                sideOffset={6}
                className="z-50 max-w-56 rounded-md bg-ink px-2.5 py-2 text-xs leading-5 text-white"
              >
                {block.description}
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        ))}
        {selected !== 'inspect' &&
          selected !== 'erase' &&
          BLOCK_BY_KIND[selected].directional && (
            <div className={cn('grid gap-1', compact ? 'col-span-6 grid-cols-6' : 'col-span-2 grid-cols-3')}>
              <button
                type="button"
                disabled={disabled}
                aria-pressed={autoFacing}
                title="放置时朝向玩家"
                onClick={() => onAutoFacingChange(!autoFacing)}
                className={cn(
                  'col-span-full flex h-8 items-center justify-center gap-1 border font-mono text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal disabled:opacity-40',
                  autoFacing ? 'border-ink bg-ink text-white' : 'border-ink/15 bg-white/45 text-ink',
                )}
              >
                <Crosshair size={12} />
                朝向玩家
              </button>
              {DIRECTIONS.map((direction) => (
                <button
                  key={direction.value}
                  type="button"
                  disabled={disabled}
                  onClick={() => onFacingChange(direction.value)}
                  className={cn(
                    'h-8 border font-mono text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal disabled:opacity-40',
                    facing === direction.value
                      ? 'border-ink bg-ink text-white'
                      : 'border-ink/15 bg-white/45 text-ink',
                  )}
                >
                  {direction.label}
                </button>
              ))}
            </div>
          )}
      </div>
    </Tooltip.Provider>
  )
}

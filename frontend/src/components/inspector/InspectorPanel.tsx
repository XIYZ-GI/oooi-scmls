import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Box, ChevronDown, Radio, Trash2, Zap } from 'lucide-react'
import { OverlayScrollbarsComponent } from 'overlayscrollbars-react'

import { BLOCKS, BLOCK_BY_KIND, DIRECTIONS, cn } from '@/lib'
import type { BlockSpec, Direction, PlacedBlock } from '@/types'

interface InspectorPanelProps {
  block: PlacedBlock | null
  disabled?: boolean
  onUpdate: (spec: BlockSpec) => void
  onDelete: () => void
}

const PHASE_LABELS: Record<string, string> = {
  retracted: '完全收回',
  extension_pending: '等待伸出',
  extending: '伸出中',
  extended: '完全伸出',
  retraction_pending: '等待收回',
  retracting: '收回中',
  blocked: '推动受阻',
  idle: '关闭',
  pulse_pending: '等待脉冲',
  pulsing: '输出脉冲',
}

export function InspectorPanel({ block, disabled, onUpdate, onDelete }: InspectorPanelProps) {
  if (!block) {
    return (
      <div className="flex h-full min-h-40 flex-col items-center justify-center px-6 text-center text-ink/45">
        <Box size={24} strokeWidth={1.4} />
        <p className="mt-3 text-sm">未选择方块</p>
      </div>
    )
  }

  const definition = BLOCK_BY_KIND[block.kind]
  const phase = block.piston_phase ?? block.observer_phase

  return (
    <OverlayScrollbarsComponent className="h-full" defer>
      <div className="divide-y divide-ink/10">
        <section className="p-4">
          <div className="flex items-center gap-3">
            <img
              src={definition.texture}
              alt=""
              className="h-10 w-10 [image-rendering:pixelated]"
            />
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-ink">{definition.label}</h2>
              <p className="mt-0.5 font-mono text-[11px] text-ink/50">ID {block.id}</p>
            </div>
            <button
              type="button"
              aria-label="删除方块"
              disabled={disabled}
              onClick={onDelete}
              className="ml-auto flex h-9 w-9 items-center justify-center border border-ink/15 text-signal hover:bg-signal/10 disabled:opacity-35"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </section>

        <section className="space-y-3 p-4">
          <PanelLabel>方块类型</PanelLabel>
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                type="button"
                disabled={disabled}
                className="flex h-10 w-full items-center border border-ink/15 bg-white/60 px-3 text-sm text-ink disabled:opacity-40"
              >
                {definition.label}
                <ChevronDown size={15} className="ml-auto" />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content className="z-50 max-h-72 min-w-56 overflow-auto border border-ink/15 bg-white p-1 shadow-xl">
                {BLOCKS.map((item) => (
                  <DropdownMenu.Item
                    key={item.kind}
                    onSelect={() => onUpdate({ kind: item.kind, facing: block.facing })}
                    className="flex cursor-default items-center px-2 py-2 text-sm outline-none hover:bg-frost"
                  >
                    <img src={item.texture} alt="" className="mr-2 h-6 w-6 [image-rendering:pixelated]" />
                    {item.label}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </section>

        <section className="p-4">
          <PanelLabel>坐标</PanelLabel>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {(['x', 'y', 'z'] as const).map((axis) => (
              <div key={axis} className="border border-ink/15 bg-white/45 px-2 py-2 text-center">
                <span className="block font-mono text-[10px] uppercase text-ink/45">{axis}</span>
                <span className="font-mono text-sm tabular-nums text-ink">{block.position[axis]}</span>
              </div>
            ))}
          </div>
        </section>

        {definition.directional && (
          <section className="p-4">
            <PanelLabel>朝向</PanelLabel>
            <div className="mt-3 grid grid-cols-3 gap-1.5">
              {DIRECTIONS.map((direction) => (
                <button
                  key={direction.value}
                  type="button"
                  disabled={disabled}
                  onClick={() =>
                    onUpdate({ kind: block.kind, facing: direction.value as Direction })
                  }
                  className={cn(
                    'h-9 border font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal disabled:opacity-40',
                    block.facing === direction.value
                      ? 'border-ink bg-ink text-white'
                      : 'border-ink/15 bg-white/45 text-ink hover:bg-white',
                  )}
                >
                  {direction.label}
                </button>
              ))}
            </div>
          </section>
        )}

        <section className="space-y-2 p-4 text-sm">
          <PanelLabel>引擎状态</PanelLabel>
          <StatusRow icon={Zap} label="普通信号" active={block.powered} />
          <StatusRow icon={Radio} label="强充能" active={block.strongly_powered} />
          {phase && (
            <div className="flex items-center border-t border-ink/10 pt-2 text-xs">
              <span className="text-ink/55">阶段</span>
              <span className="ml-auto font-medium text-ink">
                {PHASE_LABELS[phase.phase] ?? phase.phase}
              </span>
            </div>
          )}
        </section>
      </div>
    </OverlayScrollbarsComponent>
  )
}

function PanelLabel({ children }: { children: React.ReactNode }) {
  return <h3 className="text-[11px] font-semibold text-ink/55">{children}</h3>
}

function StatusRow({
  icon: Icon,
  label,
  active,
}: {
  icon: typeof Zap
  label: string
  active: boolean
}) {
  return (
    <div className="flex items-center py-1 text-xs text-ink">
      <Icon size={14} className={active ? 'text-signal' : 'text-ink/30'} />
      <span className="ml-2">{label}</span>
      <span className={cn('ml-auto font-medium', active ? 'text-signal' : 'text-ink/45')}>
        {active ? '有效' : '无'}
      </span>
    </div>
  )
}


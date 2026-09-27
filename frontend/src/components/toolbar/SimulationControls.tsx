import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import * as Tooltip from '@radix-ui/react-tooltip'
import {
  Gauge,
  Pause,
  Play,
  Redo2,
  RotateCcw,
  StepForward,
  Trash2,
  Undo2,
} from 'lucide-react'

import { cn } from '@/lib'

interface SimulationControlsProps {
  tick: number
  running: boolean
  busy: boolean
  speed: number
  canReset: boolean
  canUndo: boolean
  canRedo: boolean
  onToggleRunning: () => void
  onStep: () => void
  onReset: () => void
  onClear: () => void
  onUndo: () => void
  onRedo: () => void
  onSpeedChange: (speed: number) => void
}

const SPEEDS = [1, 2, 4, 10, 20]

export function SimulationControls(props: SimulationControlsProps) {
  const iconButton =
    'flex h-8 w-8 shrink-0 items-center justify-center border border-ink/15 bg-white/55 text-ink transition-colors hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal disabled:opacity-35 sm:h-9 sm:w-9'

  return (
    <Tooltip.Provider delayDuration={250}>
      <div className="flex shrink-0 items-center gap-0.5 sm:gap-1.5">
        <div
          data-testid="simulation-tick"
          title={`游戏刻 ${props.tick}`}
          className="h-8 w-10 shrink-0 truncate border border-ink/15 bg-white/45 px-1 text-center font-mono text-[11px] leading-8 tabular-nums text-ink sm:mr-1 sm:h-9 sm:w-auto sm:min-w-[76px] sm:px-2 sm:text-sm sm:leading-9"
        >
          T {props.tick}
        </div>
        <ControlTip label={props.running ? '暂停' : '运行'}>
          <button
            type="button"
            className={cn(iconButton, props.running && 'border-signal bg-signal text-white')}
            disabled={props.busy && !props.running}
            onClick={props.onToggleRunning}
            aria-label={props.running ? '暂停' : '运行'}
          >
            {props.running ? <Pause size={17} /> : <Play size={17} />}
          </button>
        </ControlTip>
        <ControlTip label="推进一刻">
          <button
            type="button"
            className={iconButton}
            disabled={props.busy || props.running}
            onClick={props.onStep}
            aria-label="推进一刻"
          >
            <StepForward size={17} />
          </button>
        </ControlTip>
        <ControlTip label="恢复检查点">
          <button
            type="button"
            className={iconButton}
            disabled={props.busy || !props.canReset}
            onClick={props.onReset}
            aria-label="恢复检查点"
          >
            <RotateCcw size={17} />
          </button>
        </ControlTip>
        <div className="hidden items-center gap-1.5 md:flex">
          <ControlTip label="撤销编辑">
            <button
              type="button"
              className={iconButton}
              disabled={props.busy || props.running || !props.canUndo}
              onClick={props.onUndo}
              aria-label="撤销编辑"
            >
              <Undo2 size={17} />
            </button>
          </ControlTip>
          <ControlTip label="重做编辑">
            <button
              type="button"
              className={iconButton}
              disabled={props.busy || props.running || !props.canRedo}
              onClick={props.onRedo}
              aria-label="重做编辑"
            >
              <Redo2 size={17} />
            </button>
          </ControlTip>
          <ControlTip label="清空世界">
            <button
              type="button"
              className={iconButton}
              disabled={props.busy || props.running}
              onClick={props.onClear}
              aria-label="清空世界"
            >
              <Trash2 size={17} />
            </button>
          </ControlTip>
        </div>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button type="button" className={iconButton} aria-label="运行速度">
              <Gauge size={17} />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={6}
              className="z-50 min-w-32 border border-ink/15 bg-white p-1 shadow-xl"
            >
              {SPEEDS.map((speed) => (
                <DropdownMenu.Item
                  key={speed}
                  onSelect={() => props.onSpeedChange(speed)}
                  className={cn(
                    'cursor-default px-3 py-2 text-sm outline-none hover:bg-frost',
                    props.speed === speed && 'bg-frost font-semibold text-signal',
                  )}
                >
                  {speed} 游戏刻/秒
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </Tooltip.Provider>
  )
}

function ControlTip({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="z-50 rounded-md bg-ink px-2 py-1 text-xs text-white">
          {label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

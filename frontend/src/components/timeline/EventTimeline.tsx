import { useAutoAnimate } from '@formkit/auto-animate/react'
import { Activity, Box, Move3d, Radio, Zap } from 'lucide-react'
import { OverlayScrollbarsComponent } from 'overlayscrollbars-react'

import { cn } from '@/lib'
import type { Position, SimulationEvent } from '@/types'

interface EventTimelineProps {
  tick: number
  events: SimulationEvent[]
  onSelectPosition: (position: Position) => void
}

export function EventTimeline({ tick, events, onSelectPosition }: EventTimelineProps) {
  const [parent] = useAutoAnimate<HTMLDivElement>({ duration: 160 })
  const visible = events.slice(-80).reverse()

  return (
    <section className="flex h-full w-full min-h-0 min-w-0 max-w-full overflow-hidden border-t border-ink/15 bg-frost/95">
      <div className="flex w-24 shrink-0 flex-col justify-between border-r border-ink/15 px-3 py-3 md:w-36">
        <div>
          <p className="text-[10px] font-semibold text-ink/45">事件轨道</p>
          <p className="mt-1 font-mono text-xl font-semibold tabular-nums text-ink">T {tick}</p>
        </div>
        <p className="font-mono text-[10px] text-ink/45">{events.length} 条记录</p>
      </div>
      <OverlayScrollbarsComponent className="min-w-0 flex-1 overflow-hidden" options={{ scrollbars: { autoHide: 'leave' } }}>
        <div ref={parent} className="flex min-h-full min-w-max items-stretch">
          {visible.length === 0 ? (
            <div className="flex min-w-52 items-center px-5 text-xs text-ink/40">
              <Activity size={15} className="mr-2" />
              当前没有状态事件
            </div>
          ) : (
            visible.map((event) => (
              <EventCell
                key={event.sequence}
                event={event}
                onSelectPosition={onSelectPosition}
              />
            ))
          )}
        </div>
      </OverlayScrollbarsComponent>
    </section>
  )
}

function EventCell({
  event,
  onSelectPosition,
}: {
  event: SimulationEvent
  onSelectPosition: (position: Position) => void
}) {
  const Icon = event.kind.includes('observer')
    ? Radio
    : event.kind.includes('piston')
      ? Zap
      : event.kind === 'block_moved'
        ? Move3d
        : Box
  const actionable = event.position !== null

  return (
    <button
      type="button"
      disabled={!actionable}
      onClick={() => event.position && onSelectPosition(event.position)}
      className={cn(
        'flex w-52 shrink-0 flex-col border-r border-ink/10 px-3 py-3 text-left outline-none transition-colors',
        actionable ? 'hover:bg-white/70 focus-visible:bg-white' : 'cursor-default',
      )}
    >
      <span className="flex items-center font-mono text-[10px] text-ink/45">
        <Icon size={13} className="mr-1.5 text-signal" />T {event.tick}
        {event.block_id !== null && <span className="ml-auto">#{event.block_id}</span>}
      </span>
      <span className="mt-2 line-clamp-2 text-xs leading-5 text-ink">
        {eventMessage(event)}
      </span>
    </button>
  )
}

function eventMessage(event: SimulationEvent): string {
  const coordinate = (position: Position | null) =>
    position ? `(${position.x}, ${position.y}, ${position.z})` : '未知坐标'
  if (event.kind === 'block_placed') {
    return `在 ${coordinate(event.position)} 放置方块 #${event.block_id}`
  }
  if (event.kind === 'block_removed') {
    return `移除 ${coordinate(event.position)} 的方块 #${event.block_id}`
  }
  if (event.kind === 'block_moved') {
    return `方块 #${event.block_id} 从 ${coordinate(event.from)} 移动到 ${coordinate(event.to)}`
  }
  return event.message
}

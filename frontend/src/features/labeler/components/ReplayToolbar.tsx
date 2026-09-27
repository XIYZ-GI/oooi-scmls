import * as Menu from '@radix-ui/react-dropdown-menu'
import * as Tooltip from '@radix-ui/react-tooltip'
import { ChevronLeft, ChevronRight, LoaderCircle, MoreHorizontal, Pause, Play, SquarePen } from 'lucide-react'
import type { ReactNode } from 'react'
import type { useLabelReplay } from '../hooks/useLabelReplay'

export function ReplayToolbar({ replay, showFullLoad, onLoadToggle, onResetCamera, mobileActions }: {
  replay: ReturnType<typeof useLabelReplay>
  showFullLoad: boolean
  onLoadToggle: () => void
  onResetCamera: () => void
  mobileActions: ReactNode
}) {
  const buttonClass = 'flex h-8 w-7 shrink-0 items-center justify-center rounded-md border border-ink/15 bg-white text-ink/80 hover:bg-sky-50 disabled:opacity-40'
  const button = (label: string, icon: ReactNode, action: () => void, disabled = false) => (
    <Tooltip.Root><Tooltip.Trigger asChild><button type="button" className={buttonClass} aria-label={label} disabled={disabled} onClick={action}>{icon}</button></Tooltip.Trigger>
      <Tooltip.Portal><Tooltip.Content sideOffset={5} className="z-50 rounded bg-white px-2 py-1 text-xs text-ink shadow">{label}</Tooltip.Content></Tooltip.Portal>
    </Tooltip.Root>
  )
  return <Tooltip.Provider delayDuration={300}>
    <div className="flex h-11 min-w-0 shrink-0 items-center gap-0.5 overflow-hidden border-t border-ink/15 bg-frost px-1" aria-label="打标运行工具栏">
      {button('返回标注', <SquarePen size={15} />, replay.clear)}
      {button('后退一刻', <ChevronLeft size={15} />, () => void replay.seek(replay.index - 1), !replay.info || replay.index === 0)}
      {button(replay.playing ? '暂停运行' : '播放运行', replay.loading ? <LoaderCircle size={15} className="animate-spin" /> : replay.playing ? <Pause size={15} /> : <Play size={15} />, () => replay.playing ? replay.pause() : void replay.start(), replay.loading)}
      {button('前进一刻', <ChevronRight size={15} />, () => void replay.seek(replay.index + 1), !replay.info || replay.index >= replay.info.frameCount - 1)}
      <span className="w-[72px] shrink-0 whitespace-nowrap text-center text-[10px] tabular-nums" aria-label="当前运行刻" role="status">{replay.info ? `${replay.frame?.snapshot.tick ?? 0}/${replay.info.result.simulatedTicks} 刻` : '载入中'}</span>
      <input aria-label="运行进度" type="range" min={0} max={Math.max(1, (replay.info?.frameCount ?? 1) - 1)} value={replay.index} disabled={!replay.info}
        className="h-8 min-w-0 flex-1 accent-sky-700" onChange={event => void replay.seek(Number(event.target.value))} />
      <Menu.Root><Menu.Trigger className={buttonClass} aria-label="运行设置" title="运行设置"><MoreHorizontal size={16} /></Menu.Trigger>
        <Menu.Portal><Menu.Content side="top" sideOffset={6} className="z-50 min-w-40 rounded-md border border-ink/15 bg-white p-1 text-xs shadow-lg">
          <Menu.Item className="cursor-pointer rounded px-3 py-2 outline-none focus:bg-sky-50" onSelect={() => void replay.seek(0)}>回到第0刻</Menu.Item>
          <Menu.Item className="cursor-pointer rounded px-3 py-2 outline-none focus:bg-sky-50" onSelect={onResetCamera}>重置视角</Menu.Item>
          <Menu.CheckboxItem className="cursor-pointer rounded px-3 py-2 outline-none focus:bg-sky-50 data-[state=checked]:bg-sky-100" checked={showFullLoad} onCheckedChange={onLoadToggle}>显示全部负载</Menu.CheckboxItem>
          <Menu.Separator className="my-1 h-px bg-ink/10" />
          <Menu.RadioGroup value={String(replay.speed)} onValueChange={value => replay.setSpeed(Number(value))}>
            {[1, 5, 10, 20].map(value => <Menu.RadioItem key={value} value={String(value)} className="cursor-pointer rounded px-3 py-2 outline-none focus:bg-sky-50 data-[state=checked]:bg-sky-100">{value} 刻/秒</Menu.RadioItem>)}
          </Menu.RadioGroup>
        </Menu.Content></Menu.Portal>
      </Menu.Root>
      <div className="contents lg:hidden">{mobileActions}</div>
    </div>
  </Tooltip.Provider>
}

import { useMemo } from 'react'
import { Crosshair, Eraser, Scan } from 'lucide-react'
import { cn } from '@/lib'
import type { LabelSample, MarkTool, NormalizedStructure } from '../types'
import { BUTTON_CLASS } from '../constants'
import { columnRear } from '../utils'
import { targetFailed } from '../utils/targetStatus'

export function SectionGrid({
  sample,
  shape,
  tool,
  onTool,
  onMark,
}: {
  sample: LabelSample
  shape: NormalizedStructure
  tool: MarkTool
  onTool: (tool: MarkTool) => void
  onMark: (x: number, y: number) => void
}) {
  const rear = useMemo(
    () =>
      new Set(
        shape.blocks
          .filter(
            (block) =>
              block.layer === 0 && block.position.z === columnRear(shape, block.position),
          )
          .map((block) => `${block.position.x},${block.position.y}`),
      ),
    [shape],
  )
  const targets = useMemo(
    () => new Set(sample.targets.map((target) => `${target.x},${target.y}`)),
    [sample.targets],
  )
  return (
    <section className="space-y-3">
      <div className="flex gap-1" aria-label="标注工具">
        {(
          [
            { value: 'target', label: '目标点', icon: Scan },
            { value: 'push', label: '推动点', icon: Crosshair },
            { value: 'erase', label: '擦除', icon: Eraser },
          ] as const
        ).map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            aria-pressed={tool === value}
            onClick={() => onTool(value)}
            className={cn(
              BUTTON_CLASS,
              'flex-1 px-2 text-xs',
              tool === value && 'border-sky-500 bg-sky-100',
            )}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>
      <div
        className="max-h-72 overflow-auto rounded-md border border-ink/15 bg-white p-2"
        aria-label="目标截面"
      >
        <div
          className="grid w-max gap-1"
          style={{ gridTemplateColumns: `repeat(${shape.width}, 40px)` }}
        >
          {Array.from(
            { length: shape.height },
            (_, row) => shape.height - row - 1,
          ).flatMap((y) =>
            Array.from({ length: shape.width }, (_, x) => {
              const target = targets.has(`${x},${y}`)
              const result = sample.timing?.targets.find(
                (point) => point.x === x && point.y === y,
              )
              const push =
                sample.pushPoint?.x === x && sample.pushPoint?.y === y
              const failed = targetFailed(result)
              return (
                <button
                  key={`${x},${y}`}
                  type="button"
                  aria-label={`坐标 ${x},${y}${target ? '，目标点' : ''}${push ? '，推动点' : ''}${failed ? '，未通过' : ''}`}
                  aria-pressed={!!target || push}
                  onClick={() => onMark(x, y)}
                  className={cn(
                    'relative h-10 w-10 border text-sm hover:bg-sky-50',
                    failed ? 'border-purple-500 bg-purple-200 text-purple-950 hover:bg-purple-100' : target
                      ? 'border-sky-300 bg-sky-100 text-sky-900'
                      : 'border-ink/15 bg-white text-ink/40',
                    push && 'ring-2 ring-inset ring-red-500',
                  )}
                >
                  {(target && result?.order) || (
                    <span className="text-[9px]">
                      {x},{y}
                    </span>
                  )}
                  {rear.has(`${x},${y}`) && (
                    <span className="absolute bottom-1 left-1 h-1 w-1 bg-ink/40" />
                  )}
                </button>
              )
            }),
          )}
        </div>
      </div>
    </section>
  )
}

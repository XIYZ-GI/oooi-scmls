import { useEffect, useState } from 'react'
import { cn } from '@/lib'
import { FIELD } from './constants'

/**
 * 数字输入：清空时保持为空，只有输入合法整数才提交；失焦时把越界值收到范围内、
 * 空值或非数字则恢复为当前值。避免删到一半就被强制回填最小值。
 */
export function NumberField({ aria, value, min, max, disabled, className, onCommit }: {
  aria: string; value: number; min: number; max: number; disabled?: boolean
  className?: string; onCommit: (value: number) => void
}) {
  const [text, setText] = useState(String(value))
  const [editing, setEditing] = useState(false)
  useEffect(() => { if (!editing) setText(String(value)) }, [value, editing])
  const change = (raw: string) => {
    setText(raw)
    const parsed = Number(raw)
    if (raw.trim() !== '' && Number.isInteger(parsed) && parsed >= min && parsed <= max) onCommit(parsed)
  }
  const blur = () => {
    const parsed = Number(text)
    setEditing(false)
    if (text.trim() !== '' && Number.isFinite(parsed)) onCommit(Math.max(min, Math.min(max, Math.trunc(parsed))))
  }
  return <input aria-label={aria} title={aria} className={cn(FIELD, 'text-center', className)} type="text"
    inputMode="numeric" value={text} disabled={disabled}
    onChange={event => change(event.target.value)}
    onFocus={() => setEditing(true)}
    onBlur={blur}
    onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur() }} />
}

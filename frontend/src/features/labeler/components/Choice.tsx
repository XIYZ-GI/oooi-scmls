import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Check, ChevronDown } from 'lucide-react'
import { BUTTON_CLASS } from '../constants'

export function Choice<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        className={`${BUTTON_CLASS} w-full justify-between`}
        aria-label={label}
      >
        {options.find((item) => item.value === value)?.label}
        <ChevronDown size={15} />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="z-[70] min-w-40 rounded-md border border-ink/20 bg-white p-1 shadow-lg"
          sideOffset={4}
        >
          <DropdownMenu.RadioGroup
            value={value}
            onValueChange={(next) => onChange(next as T)}
          >
            {options.map((option) => (
              <DropdownMenu.RadioItem
                key={option.value}
                value={option.value}
                className="flex min-h-10 cursor-pointer items-center gap-2 rounded px-2 text-sm outline-none data-[highlighted]:bg-sky-50"
              >
                <span className="w-4">
                  <DropdownMenu.ItemIndicator>
                    <Check size={14} />
                  </DropdownMenu.ItemIndicator>
                </span>
                {option.label}
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

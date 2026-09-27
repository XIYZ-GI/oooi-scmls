import { useEffect, useState, type RefObject } from 'react'

export function useViewportScale(container: RefObject<HTMLDivElement | null>) {
  const [scale, setScale] = useState(1)
  useEffect(() => {
    const element = container.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width > 0 && height > 0) setScale(Math.max(1, height / width))
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [container])
  return scale
}

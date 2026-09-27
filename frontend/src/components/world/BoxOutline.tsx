import { useEffect, useMemo } from 'react'
import { BoxGeometry, EdgesGeometry } from 'three'

export function BoxOutline({
  size = 0.96,
  color,
}: {
  size?: number
  color: string
}) {
  const geometry = useMemo(() => {
    const box = new BoxGeometry(size, size, size)
    const edges = new EdgesGeometry(box)
    box.dispose()
    return edges
  }, [size])
  useEffect(() => () => geometry.dispose(), [geometry])
  return (
    <lineSegments geometry={geometry} raycast={() => null}>
      <lineBasicMaterial color={color} />
    </lineSegments>
  )
}

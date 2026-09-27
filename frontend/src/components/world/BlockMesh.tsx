import { useTexture } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { ThreeEvent } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Group, NearestFilter, Quaternion, SRGBColorSpace } from 'three'
import { blockTextures } from '@/lib'
import type { PlacedBlock, Position } from '@/types'

import { addPosition, directionQuaternion, oppositeDirection } from './utils'
import type { SwipeDirection, TapGesture } from './useTapGesture'
import { orientPistonSideUVs } from './pistonTextureUVs'
import { BoxOutline } from './BoxOutline'

interface BlockMeshProps {
  block: PlacedBlock
  renderPosition: [number, number, number]
  selected: boolean
  disabled: boolean
  gesture: TapGesture
  onSelect: (block: PlacedBlock) => void
  onFaceAction: (block: PlacedBlock, adjacent: Position, camera: ThreeEvent<PointerEvent>['camera']) => void
  onErase: (block: PlacedBlock) => void
  onSwipe: (block: PlacedBlock, direction: SwipeDirection, event: ThreeEvent<PointerEvent>) => void
}

export function BlockMesh({
  block,
  renderPosition,
  selected,
  disabled,
  gesture,
  onSelect,
  onFaceAction,
  onErase,
  onSwipe,
}: BlockMeshProps) {
  const [hovered, setHovered] = useState(false)
  const observerLit = block.observer_phase?.phase === 'pulsing'
  const paths = useMemo(() => blockTextures(block.kind, observerLit), [block.kind, observerLit])
  const textures = useTexture(paths)
  const visualFacing =
    block.kind === 'observer' ? oppositeDirection(block.facing) : block.facing
  const quaternion = useMemo(() => directionQuaternion(visualFacing), [visualFacing])
  const group = useRef<Group>(null)
  const animation = useRef<{ from: Quaternion; started: number } | null>(null)
  useEffect(() => {
    const node = group.current
    if (!node) return
    const current = node.quaternion.clone()
    if (current.angleTo(quaternion) < 1e-3) return
    animation.current = { from: current, started: performance.now() }
  }, [quaternion])
  useFrame(() => {
    const node = group.current
    const active = animation.current
    if (!node || !active) return
    const progress = Math.min(1, (performance.now()-active.started)/180)
    const eased = 1-Math.pow(1-progress, 3)
    node.quaternion.slerpQuaternions(active.from, quaternion, eased)
    if (progress >= 1) {
      node.quaternion.copy(quaternion)
      animation.current = null
    }
  })
  const transparent = ['glass', 'slime_block', 'honey_block'].includes(block.kind)
  for (const texture of textures) {
    texture.magFilter = NearestFilter
    texture.minFilter = NearestFilter
    texture.colorSpace = SRGBColorSpace
  }

  const handlePointerDown = (event: ThreeEvent<PointerEvent>) => {
    if (disabled) return
    if (!event.face) {
      gesture.begin(event, () => onSelect(block))
      return
    }
    const normal = event.face.normal
      .clone()
      .transformDirection(event.object.matrixWorld)
      .round()
    const adjacent = addPosition(block.position, normal)
    gesture.begin(event, () => onFaceAction(block, adjacent, event.camera),
      (direction, swipeEvent) => onSwipe(block, direction, swipeEvent))
  }

  const handleContextMenu = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    event.nativeEvent.preventDefault()
    gesture.cancelAll()
    if (!disabled) onErase(block)
  }

  return (
    <group ref={group} position={renderPosition} quaternion={quaternion}>
      <mesh
        castShadow
        receiveShadow
        onPointerDown={handlePointerDown}
        onPointerMove={gesture.move}
        onPointerUp={gesture.end}
        onPointerCancel={gesture.cancel}
        onContextMenu={handleContextMenu}
        onPointerEnter={() => setHovered(true)}
        onPointerLeave={() => setHovered(false)}
      >
        <boxGeometry key={block.kind} args={[0.94, 0.94, 0.94]} onUpdate={block.kind === 'piston' || block.kind === 'sticky_piston' ? orientPistonSideUVs : undefined} />
        {textures.map((texture, index) => (
          <meshStandardMaterial
            key={`${texture.uuid}-${index}`}
            attach={`material-${index}`}
            map={texture}
            transparent={transparent}
            opacity={block.kind === 'glass' ? 0.5 : transparent ? 0.88 : 1}
            depthWrite={block.kind !== 'glass'}
            emissive={block.powered || block.strongly_powered ? '#8F2424' : '#000000'}
            emissiveIntensity={block.powered || block.strongly_powered ? 0.32 : 0}
            roughness={0.84}
          />
        ))}
        {(selected || hovered) && (
          <BoxOutline color={selected ? '#C84C4C' : '#477B8A'} />
        )}
      </mesh>
      {block.strongly_powered && (
        <mesh position={[0, 0.51, 0]}>
          <planeGeometry args={[0.54, 0.54]} />
          <meshBasicMaterial color="#D85B55" transparent opacity={0.75} />
        </mesh>
      )}
    </group>
  )
}

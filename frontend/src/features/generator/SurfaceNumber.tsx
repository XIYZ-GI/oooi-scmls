import { useEffect, useMemo } from 'react'
import { CanvasTexture, SRGBColorSpace } from 'three'
import { groupColor } from './constants'

// 数字绘制成方块表面的贴图，随模型透视、遮挡和旋转，不跟随镜头。
export function SurfaceNumber({ order, offset = .056, size = .78 }: { order: number; offset?: number; size?: number }) {
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 128; canvas.height = 128
    const context = canvas.getContext('2d')!
    context.fillStyle = groupColor(order); context.fillRect(0, 0, 128, 128)
    context.fillStyle = '#183f50'; context.font = 'bold 86px system-ui'
    context.textAlign = 'center'; context.textBaseline = 'middle'; context.fillText(String(order), 64, 68)
    const value = new CanvasTexture(canvas); value.colorSpace = SRGBColorSpace
    return value
  }, [order])
  useEffect(() => () => texture.dispose(), [texture])
  return <>{[1, -1].map(side => <mesh key={side} position={[0, 0, side*offset]} rotation={[0, side === 1 ? 0 : Math.PI, 0]} raycast={() => null}>
    <planeGeometry args={[size, size]} /><meshBasicMaterial map={texture} toneMapped={false} />
  </mesh>)}</>
}

import type { BoxGeometry } from 'three'

export function orientPistonSideUVs(geometry: BoxGeometry) {
  if (geometry.userData.pistonSideUVs) return
  const uv = geometry.attributes.uv
  // BoxGeometry 的前四面依次为 +X、-X、+Y、-Y，贴图木质边缘统一对齐局部 +Z。
  for (let face = 0; face < 4; face += 1) {
    for (let corner = 0; corner < 4; corner += 1) {
      const index = face * 4 + corner
      const u = uv.getX(index),
        v = uv.getY(index)
      if (face === 0) uv.setXY(index, v, 1 - u)
      else if (face === 1) uv.setXY(index, 1 - v, u)
      else if (face === 2) uv.setXY(index, 1 - u, 1 - v)
    }
  }
  uv.needsUpdate = true
  geometry.userData.pistonSideUVs = true
}

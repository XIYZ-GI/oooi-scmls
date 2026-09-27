import { Navigation, LoaderCircle } from 'lucide-react'
import { useRef, useState, type RefObject } from 'react'
import { Vector3, type Camera } from 'three'
import { toast } from 'sonner'
import type { Direction } from '@/types'
import { COMPACT_TOOL_CLASS } from '../constants'
import { directionFromCamera } from '../utils'

export function CameraDirectionControl({ forward, onChange, cameraRef }: {
  forward: Direction
  onChange: (direction: Direction) => Promise<void>
  cameraRef: RefObject<Camera | null>
}) {
  const locked = useRef(false)
  const [saving, setSaving] = useState(false)
  const apply = async () => {
    if (locked.current) return
    const camera = cameraRef.current
    if (!camera) { toast.info('三维预览正在加载，请稍后再试'); return }
    locked.current = true
    setSaving(true)
    try {
      await onChange(directionFromCamera(camera.getWorldDirection(new Vector3()), forward))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '方向保存失败，请重试')
    } finally {
      locked.current = false
      setSaving(false)
    }
  }
  return (
        <button
          type="button"
          className={`${COMPACT_TOOL_CLASS} border-sky-400`}
          aria-label="按当前视角设为前进方向"
          aria-busy={saving}
          disabled={saving}
          onClick={() => void apply()}
        >
          {saving ? <LoaderCircle size={16} className="animate-spin" /> : <Navigation size={16} />}
        </button>
  )
}

import { useThree } from '@react-three/fiber'
import { useEffect, type RefObject } from 'react'
import type { Camera } from 'three'

export function AnnotationCameraBridge({ cameraRef }: { cameraRef: RefObject<Camera | null> }) {
  const camera = useThree((state) => state.camera)
  useEffect(() => {
    cameraRef.current = camera
    return () => { if (cameraRef.current === camera) cameraRef.current = null }
  }, [camera, cameraRef])
  return null
}

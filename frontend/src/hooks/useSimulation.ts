import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { createSession, sendCommand, sessionSocketUrl } from '@/lib'
import type { EngineCommand, SimulationSnapshot } from '@/types'

type ConnectionState = 'loading' | 'connected' | 'reconnecting' | 'error'

export function useSimulation() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>('loading')
  const [isApplying, setIsApplying] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)
  const commandQueueRef = useRef<Promise<unknown>>(Promise.resolve())
  const pendingCommandsRef = useRef(0)

  const connectSocket = useCallback((id: string) => {
    socketRef.current?.close()
    const socket = new WebSocket(sessionSocketUrl(id))
    socketRef.current = socket
    socket.onopen = () => setConnectionState('connected')
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as {
        type: string
        snapshot?: SimulationSnapshot
      }
      if (payload.type === 'snapshot' && payload.snapshot) setSnapshot(payload.snapshot)
    }
    socket.onclose = () => setConnectionState('reconnecting')
    socket.onerror = () => setConnectionState('error')
  }, [])

  const initialize = useCallback(async () => {
    setConnectionState('loading')
    try {
      const created = await createSession()
      setSessionId(created.session_id)
      setSnapshot(created.snapshot)
      connectSocket(created.session_id)
    } catch (error) {
      setConnectionState('error')
      toast.error(error instanceof Error ? error.message : '无法创建模拟会话')
    }
  }, [connectSocket])

  useEffect(() => {
    void initialize()
    return () => socketRef.current?.close()
  }, [initialize])

  const apply = useCallback(
    (command: EngineCommand): Promise<SimulationSnapshot | null> => {
      if (!sessionId) return Promise.resolve(null)
      pendingCommandsRef.current += 1
      setIsApplying(true)

      const execute = async () => {
        try {
          const next = await sendCommand(sessionId, command)
          setSnapshot(next)
          return next
        } catch (error) {
          toast.error(error instanceof Error ? error.message : '引擎命令执行失败')
          return null
        } finally {
          pendingCommandsRef.current -= 1
          if (pendingCommandsRef.current === 0) setIsApplying(false)
        }
      }

      const result = commandQueueRef.current.then(execute, execute)
      commandQueueRef.current = result.then(() => undefined)
      return result
    },
    [sessionId],
  )

  return {
    sessionId,
    snapshot,
    connectionState,
    isApplying,
    apply,
    reconnect: initialize,
  }
}

import type { EngineCommand, SimulationSnapshot } from '@/types'

interface CreatedSession {
  session_id: string
  snapshot: SimulationSnapshot
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null
  throw new Error(payload?.detail || `请求失败（${response.status}）`)
}

export async function createSession(): Promise<CreatedSession> {
  const response = await fetch('/api/sessions', { method: 'POST' })
  return parseResponse(response)
}

export async function sendCommand(
  sessionId: string,
  command: EngineCommand,
): Promise<SimulationSnapshot> {
  const response = await fetch(`/api/sessions/${sessionId}/commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command }),
  })
  return parseResponse(response)
}

export function sessionSocketUrl(sessionId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/sessions/${sessionId}/stream`
}


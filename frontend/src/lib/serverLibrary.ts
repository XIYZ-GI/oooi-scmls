export type LibraryKind = 'samples' | 'scenes'

export interface ServerDocument {
  id: string
  name: string
  revision: number
  updatedAt: string
}

export class ServerLibraryError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

export async function libraryRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/datasets/${path}`, {
    ...init,
    headers: { ...(typeof init?.body === 'string' ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new ServerLibraryError(typeof data?.detail === 'string' ? data.detail : `服务器请求失败（${response.status}）`, response.status)
  return data as T
}

export async function downloadServerFile(path: string, filename: string) {
  const response = await fetch(`/api/datasets/${path}`)
  if (!response.ok) throw new Error('服务器导出失败，请稍后重试')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename.replace(/[\\/:*?"<>|]/g, '_')
  anchor.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

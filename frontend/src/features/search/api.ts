export async function searchRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/search${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : `请求失败（${response.status}）`)
  }
  return response.json() as Promise<T>
}

export async function searchDownload(path: string, name: string) {
  const response = await fetch(`/api/search${path}`)
  if (!response.ok) throw new Error('导出失败，请稍后重试')
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

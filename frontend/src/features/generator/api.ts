export async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api/generation'+path, {
    method, headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail :
    Array.isArray(data?.detail) ? data.detail.map((r: { msg: string }) => r.msg).join('；') : `请求失败（${response.status}）`)
  return data as T
}

/** 下载服务器生成的二进制文件（如 .mcstructure），文件名优先取响应头里的原名。 */
export async function download(path: string, fallback: string) {
  const response = await fetch('/api/generation'+path)
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(typeof data?.detail === 'string' ? data.detail : `请求失败（${response.status}）`)
  }
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(response.headers.get('Content-Disposition') ?? '')
  const name = (encoded ? decodeURIComponent(encoded[1]) : fallback).replace(/[\\/:*?"<>|]/g, '_')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

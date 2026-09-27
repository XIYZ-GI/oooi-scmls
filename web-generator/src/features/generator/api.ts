/** 生成器页面的数据入口：把原先指向服务器的 REST 路径映射到原生桥。
 *
 * 关键取舍是保留 `request(path, method, body)` 这个签名不变——原生桥本身是同步的，
 * 但页面里几十处调用点都写成 `await request(...)` 的形式，把桥的返回值包成 Promise
 * 就能一处不改地完成迁移。原生抛出的错误在这里转成 Error，交给各调用点原有的
 * catch/toast 逻辑处理。
 */

import * as bridge from '@/bridge'
import type { Draft, Job, ModelInfo, Replay, Task } from './types'

/** 把原生返回里的 `{ error }` 翻成异常，其余原样返回。 */
function unwrap<T>(value: T | { error?: string }): T {
  if (value && typeof value === 'object' && 'error' in value && value.error) throw new Error(value.error)
  return value as T
}

/** 复刻服务端的 REST 语义，只是运算发生在原生侧。 */
export async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const route = path.split('?')[0].replace(/\/+$/, '') || '/'

  if (route === '/draft') {
    if (method === 'GET') return bridge.readDraft() as T
    // 原生侧草稿只有一个版本，不做乐观锁；原样写回并返回最新内容。
    return bridge.writeDraft(body as Draft) as T
  }
  if (route === '/models') return unwrap(bridge.readModel()) as T
  if (route === '/jobs') {
    if (method === 'POST') {
      const payload = body as { task: Task; candidate_count: number; model_id: string }
      return bridge.submitJob(payload.task, payload.candidate_count, payload.model_id) as T
    }
    return bridge.listJobs() as T
  }

  const job = /^\/jobs\/([^/]+)$/.exec(route)
  if (job) {
    const id = job[1]
    if (method === 'DELETE') { bridge.deleteJob(id); return {} as T }
    if (method === 'PATCH') { return bridge.renameJob(id, (body as { name: string }).name) as T }
    return bridge.readJob(id) as T
  }
  const cancel = /^\/jobs\/([^/]+)\/cancel$/.exec(route)
  if (cancel) {
    bridge.cancelJob(cancel[1]); return bridge.readJob(cancel[1]) as T
  }
  const candidateAction = /^\/jobs\/([^/]+)\/candidates\/(\d+)\/(replay|export)$/.exec(route)
  if (candidateAction) {
    const [, id, index, action] = candidateAction
    const candidate = Number(index)
    if (action === 'replay') return bridge.readReplay(id, candidate) as T
    return bridge.exportCandidate(id, candidate, /[?&]assembly=true/.test(path)) as T
  }
  throw new Error(`本地运算环境不支持这个操作：${path}`)
}

/** 导出候选结构文件；原生侧直接写入系统下载目录，这里只返回文件名。 */
export async function download(path: string, _fallback: string): Promise<string> {
  return (await request<string>(path)) || _fallback
}

export type { Draft, Job, ModelInfo, Replay, Task }

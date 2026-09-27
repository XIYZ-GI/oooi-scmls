/** 本地桥接层：套壳网页与安卓原生侧的唯一接口。
 *
 * 分工：模型推理、红石模拟、十负载判定全部由原生侧完成；网页只负责画面与交互。
 * 因此这里不实现任何运算，只做三件事：调用桥、解析返回、把原生错误翻成中文提示。
 *
 * 网页单独在浏览器里打开时没有原生桥，此时 `available()` 返回 false，页面显示明确的
 * 提示而不是静默失败——开发阶段也能一眼看出自己没在 App 环境里。
 */

import type { Draft, Job, ModelInfo, Replay, Task } from '@/features/generator/types'

/** 原生侧暴露的方法集合；字段名与 Kotlin 侧的 `@JavascriptInterface` 一一对应。 */
export interface NativeBridge {
  /** 原生运算层版本号。 */
  version(): string
  /** 提交一次生成任务，返回任务编号。 */
  submitJob(payload: string): string
  /** 读取任务状态与结果；未完成时结果为空。 */
  readJob(jobId: string): string
  /** 取消任务。 */
  cancelJob(jobId: string): void
  /** 删除任务。 */
  deleteJob(jobId: string): void
  /** 重命名任务。 */
  renameJob(jobId: string, name: string): string
  /** 读取全部历史任务。 */
  listJobs(): string
  /** 读取需求草稿。 */
  readDraft(): string
  /** 保存需求草稿。 */
  writeDraft(payload: string): string
  /** 读取唯一的模型信息。 */
  readModel(): string
  /** 读取指定候选的逐帧回放。 */
  readReplay(jobId: string, candidate: number): string
  /** 导出候选为基岩版结构文件，返回写入手机的文件名。 */
  exportCandidate(jobId: string, candidate: number, assembly: boolean): string
  /** 查询模型权重加载状态：`loading` / `ready` / `error`。 */
  modelState(): string
}

declare global {
  interface Window {
    MCSCAI?: NativeBridge
  }
}

/** 桥是否可用；在浏览器里直接打开网页时为 false。 */
export function available(): boolean {
  return typeof window !== 'undefined' && typeof window.MCSCAI === 'object'
}

/** 读取桥，不可用时抛出带中文说明的错误。 */
function bridge(): NativeBridge {
  const value = window.MCSCAI
  if (!value) throw new Error('未检测到本地运算环境，请在 App 内使用该页面')
  return value
}

/** 解析原生返回的 JSON。 */
function parse<T>(raw: string, action: string): T {
  try {
    return JSON.parse(raw) as T
  } catch {
    throw new Error(`${action}失败：原生返回的内容无法解析`)
  }
}

/** 读取原生的字符串结果；若返回的是错误对象则抛出。 */
function unwrap(raw: string, action: string): string {
  const value = parse<string | { error?: string }>(raw, action)
  if (typeof value === 'string') return value
  if (value && typeof value === 'object' && value.error) throw new Error(value.error)
  throw new Error(`${action}失败`)
}

/** 原生运算层版本号。 */
export function version(): string {
  return bridge().version()
}

/** 模型权重加载状态。 */
export type ModelState = 'loading' | 'ready' | 'error'

/** 查询模型权重状态与说明文案。 */
export function modelState(): { state: ModelState; message: string } {
  return parse<{ state: ModelState; message: string }>(bridge().modelState(), '读取模型状态')
}

/** 读取唯一模型的信息。 */
export function readModel(): { models: ModelInfo[]; default: string } {
  return parse(bridge().readModel(), '读取模型信息')
}

/** 读取需求草稿。 */
export function readDraft(): Draft {
  return parse(bridge().readDraft(), '读取草稿')
}

/** 保存需求草稿。 */
export function writeDraft(payload: Draft): Draft {
  return parse(bridge().writeDraft(JSON.stringify(payload)), '保存草稿')
}

/** 列出历史任务。 */
export function listJobs(): Job[] {
  return parse(bridge().listJobs(), '读取历史记录')
}

/** 提交生成任务；原生侧立刻返回任务编号，进度另行轮询。 */
export function submitJob(task: Task, candidateCount: number, modelId: string): Job {
  return parse(
    bridge().submitJob(JSON.stringify({ task, candidate_count: candidateCount, model_id: modelId })),
    '提交生成任务',
  )
}

/** 读取任务状态。 */
export function readJob(jobId: string): Job {
  return parse(bridge().readJob(jobId), '读取任务状态')
}

/** 取消任务。 */
export function cancelJob(jobId: string): void {
  bridge().cancelJob(jobId)
}

/** 删除任务。 */
export function deleteJob(jobId: string): void {
  bridge().deleteJob(jobId)
}

/** 重命名任务。 */
export function renameJob(jobId: string, name: string): Job {
  return parse(bridge().renameJob(jobId, name), '重命名')
}

/** 读取回放。 */
export function readReplay(jobId: string, candidate: number): Replay {
  return parse(bridge().readReplay(jobId, candidate), '读取回放')
}

/** 导出候选结构；原生侧写入文件后返回文件名。 */
export function exportCandidate(jobId: string, candidate: number, assembly: boolean): string {
  return unwrap(bridge().exportCandidate(jobId, candidate, assembly), '导出结构')
}

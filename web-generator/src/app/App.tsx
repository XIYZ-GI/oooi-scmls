/** 套壳网页的根组件。
 *
 * 与原项目的工作台不同，这里没有模拟器、打标器和搜索页——页面只是生成器的界面，
 * 所有运算都在安卓原生侧完成。因此根组件只做两件事：确认原生桥存在，然后渲染
 * 生成器页面；桥不存在时给出明确提示，避免用户在浏览器里打开时面对一堆静默失败。
 */

import { CircleAlert, LoaderCircle } from 'lucide-react'
import { GeneratorPage } from '@/features/generator'
import { available, version } from '@/bridge'

export function App() {
  // 直接访问而非 useState：桥在页面脚本注入后就不再变化，不需要响应式。
  const ready = available()
  return <div className="flex h-dvh min-w-0 flex-col overflow-hidden bg-frost text-ink">
    {!ready && <div className="flex shrink-0 items-start gap-2 border-b border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
      <CircleAlert size={14} className="mt-0.5 shrink-0" />
      <p>未检测到本地运算环境。这个页面的模型推理、红石模拟与判定都由 App 原生侧完成，请在 App 内打开；单独用浏览器访问无法生成移动线。</p>
    </div>}
    {ready && version() && <span className="hidden">{version()}</span>}
    {ready ? <GeneratorPage /> : <div className="flex flex-1 flex-col items-center justify-center gap-2 bg-bench p-6 text-center text-sm text-ink/55">
      <LoaderCircle size={20} className="animate-spin text-sky-600" />
      <p>等待 App 注入本地运算环境…</p>
    </div>}
  </div>
}

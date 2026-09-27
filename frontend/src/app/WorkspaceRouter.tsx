import {
  Component,
  lazy,
  Suspense,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { App } from './App'

const LabelerPage = lazy(() =>
  import('@/features/labeler').then((module) => ({
    default: module.LabelerPage,
  })),
)
const SearchPage = lazy(() => import('@/features/search').then(module => ({ default: module.SearchPage })))
const GeneratorPage = lazy(() => import('@/features/generator').then(module => ({ default: module.GeneratorPage })))

class WorkspaceError extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    if (this.state.failed)
      return (
        <div className="flex h-dvh flex-col items-center justify-center gap-4 bg-frost px-6 text-sm text-ink">
          <p>页面加载失败，请刷新重试。已保存的结构和标注仍保留在服务器。</p>
          <button
            className="rounded-md border border-ink/20 bg-white px-4 py-2"
            onClick={() => window.location.reload()}
          >
            刷新页面
          </button>
          <a href="/">返回模拟器</a>
        </div>
      )
    return this.props.children
  }
}

export function WorkspaceRouter() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const listener = () => setHash(window.location.hash)
    window.addEventListener('hashchange', listener)
    return () => window.removeEventListener('hashchange', listener)
  }, [])
  return (
    <WorkspaceError key={hash}>
      <Suspense
        fallback={
          <div className="flex h-dvh animate-pulse items-center justify-center bg-frost text-sm text-ink/60">
            正在载入工作区…
          </div>
        }
      >
        {hash === '#generate' ? <GeneratorPage /> : hash === '#search' ? <SearchPage /> : hash === '#labeler' ? <LabelerPage /> : <App />}
      </Suspense>
    </WorkspaceError>
  )
}

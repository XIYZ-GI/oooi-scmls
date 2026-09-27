import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'overlayscrollbars/overlayscrollbars.css'

import { WorkspaceRouter } from '@/app'
import '@/styles/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WorkspaceRouter />
  </StrictMode>,
)

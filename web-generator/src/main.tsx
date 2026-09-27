import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'overlayscrollbars/overlayscrollbars.css'

import { App } from '@/app'
import '@/styles/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

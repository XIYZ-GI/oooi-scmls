import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8010'

  return {
    plugins: [react()],
    resolve: { alias: { '@': '/src' } },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': { target, changeOrigin: true },
        '/ws': { target, ws: true, changeOrigin: true },
      },
    },
    build: {
      chunkSizeWarningLimit: 1000,
    },
  }
})

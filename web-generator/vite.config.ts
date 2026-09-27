import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // 页面挂载在 WebViewAssetLoader 的 /assets/www/ 下，资源路径必须相对页面计算。
  base: './',
  resolve: { alias: { '@': '/src' } },
  build: {
    chunkSizeWarningLimit: 1600,
    // 安卓侧的 WebView 版本随系统更新，直接对齐现代语法，不做多余降级。
    target: 'es2020',
  },
})

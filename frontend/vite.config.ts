import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // dev 环境把 /api 代理到本地后端，避免跨域
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})

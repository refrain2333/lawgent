import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())
  const apiTarget = env.VITE_API_BASE_URL || 'http://127.0.0.1:5006'
  const wsTarget  = env.VITE_WS_BASE_URL  || 'ws://127.0.0.1:5006'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      proxy: {
        '/api/v1/agent/ws': { target: wsTarget, ws: true, changeOrigin: true },
        '/api': { target: apiTarget, changeOrigin: true },
      },
    },
  }
})

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendHttpUrl = env.VITE_BACKEND_HTTP_URL || 'http://localhost:8000'
  const backendWsUrl = env.VITE_BACKEND_WS_URL || backendHttpUrl.replace(/^http/, 'ws')

  return {
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: backendHttpUrl,
          changeOrigin: true,
        },
        '/ws': {
          target: backendWsUrl,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  }
})

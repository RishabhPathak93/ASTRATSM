import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.BACKEND_URL || 'http://localhost:8000'

  return {
    plugins: [
      react()
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        '/api': {
          target: backend,
          changeOrigin: true,
        },
        '/media': {
          target: backend,
          changeOrigin: true,
        },
        '/ws': {
          target: backend.replace('http', 'ws'),
          ws: true,
          changeOrigin: true,
          rewriteWsOrigin: true,
        },
      },
    },
  }
})

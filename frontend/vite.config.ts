import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load .env / .env.local / .env.[mode] / .env.[mode].local so API_PROXY_TARGET works when you
  // run `npm run dev` (Node does not inject those into process.env automatically).
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget = env.API_PROXY_TARGET || 'http://127.0.0.1:8000'

  if (env.VITE_SUPPRESS_PROXY_LOG !== '1') {
    console.info(`[vite] /api proxy → ${apiProxyTarget}`)
  }

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        // Root probes (UPS-BE-10/11); exact paths so no SPA route is captured.
        '^/(healthz|readyz|version)$': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})

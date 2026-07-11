import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({command}) => ({
  plugins: [react()],
  // Production build is served by FastAPI under /react-assets/*, but the Vite
  // dev server must serve from root so routes like /planning work directly.
  base: command === 'build' ? '/react-assets/' : '/',
  server: {
    proxy: {
      // Keeps the dev server same-origin with FastAPI so the session cookie
      // (SameSite=Lax) is sent without needing CORS/credentials setup.
      '/api': 'http://localhost:5093',
      '/login': 'http://localhost:5093',
      '/logout': 'http://localhost:5093',
    },
  },
  build: {
    // antd + @ant-design/icons are isolated into their own vendor chunk (below) and are
    // inherently >500kB even after minification; the default warning threshold exists to
    // catch app-code bloat, not to flag a known, cached-across-routes vendor chunk.
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('antd') || id.includes('@ant-design')) return 'antd'
            if (
              id.includes('/react/') ||
              id.includes('/react-dom/') ||
              id.includes('/react-router') ||
              id.includes('/@tanstack/react-query')
            ) {
              return 'vendor'
            }
          }
        },
      },
    },
  },
}))

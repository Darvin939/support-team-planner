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
}))

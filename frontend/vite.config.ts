import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/react-assets/',
  server: {
    proxy: {
      // Keeps the dev server same-origin with FastAPI so the session cookie
      // (SameSite=Lax) is sent without needing CORS/credentials setup.
      '/api': 'http://localhost:5093',
      '/login': 'http://localhost:5093',
      '/logout': 'http://localhost:5093',
    },
  },
})

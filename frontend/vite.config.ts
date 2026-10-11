import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'
import {copyFileSync} from 'node:fs'
import type {IncomingMessage, ServerResponse} from 'node:http'
import {resolve} from 'node:path'

const copyTaskTransitions = () => ({
  name: 'copy-task-transitions',
  closeBundle() {
    copyFileSync(
      resolve(__dirname, 'src/data/taskTransitions.json'),
      resolve(__dirname, 'dist/taskTransitions.json'),
    )
  },
})

const proxyBackendAndServeAuthRoutes = () => ({
  name: 'proxy-backend-and-serve-auth-routes',
  configureServer(server: {
    config: {logger: {error: (message: string) => void}}
    middlewares: {use: (handler: (req: IncomingMessage, res: ServerResponse, next: () => void) => void) => void}
  }) {
    server.middlewares.use(async (req, res, next) => {
      if (req.method === 'GET' && (req.url === '/login' || req.url === '/logout')) {
        req.url = '/index.html'
        next()
        return
      }

      const shouldProxy = req.url?.startsWith('/api/')
        || (req.method === 'POST' && (req.url === '/login' || req.url === '/logout'))
      if (!shouldProxy) {
        next()
        return
      }

      try {
        const chunks: Buffer[] = []
        for await (const chunk of req) {
          chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
        }
        const headers = new Headers()
        for (const [name, value] of Object.entries(req.headers)) {
          if (value !== undefined && !['host', 'connection', 'content-length'].includes(name)) {
            headers.set(name, Array.isArray(value) ? value.join(', ') : value)
          }
        }
        const response = await fetch(`http://127.0.0.1:5093${req.url}`, {
          method: req.method,
          headers,
          body: chunks.length > 0 ? Buffer.concat(chunks) : undefined,
        })
        res.statusCode = response.status
        response.headers.forEach((value, name) => {
          if (name !== 'set-cookie') res.setHeader(name, value)
        })
        const cookies = response.headers.getSetCookie()
        if (cookies.length > 0) res.setHeader('set-cookie', cookies)
        res.end(Buffer.from(await response.arrayBuffer()))
      } catch (error) {
        server.config.logger.error(`Backend proxy error: ${String(error)}`)
        res.statusCode = 502
        res.end('Bad Gateway')
      }
    })
  },
})

// https://vite.dev/config/
export default defineConfig(({command}) => ({
  plugins: [proxyBackendAndServeAuthRoutes(), react(), copyTaskTransitions()],
  // Production build is served by FastAPI under /react-assets/*, but the Vite
  // dev server must serve from root so routes like /planning work directly.
  base: command === 'build' ? '/react-assets/' : '/',
  server: {
    host: '127.0.0.1',
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

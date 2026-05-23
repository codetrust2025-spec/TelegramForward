import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiPort = process.env.API_PORT || '8000'
const apiTarget = `http://127.0.0.1:${apiPort}`
const wsTarget = `ws://127.0.0.1:${apiPort}`

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 3000,
    proxy: {
      '/groups': apiTarget,
      '/account': apiTarget,
      '/login': apiTarget,
      '/message': apiTarget,
      '/start': apiTarget,
      '/stop': apiTarget,
      '/state': apiTarget,
      '/health': apiTarget,
      '/inbox': apiTarget,
      '/crm': apiTarget,
      '/stats': apiTarget,
      '/accounts': apiTarget,
      '/ws': { target: wsTarget, ws: true },
    },
  },
  build: {
    outDir: '../static',   // build output goes to /static next to server.py
    emptyOutDir: true,
  },
})

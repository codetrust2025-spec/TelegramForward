import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
  build: {
    outDir: '../static',   // build output goes to /static next to server.py
    emptyOutDir: true,
  },
})

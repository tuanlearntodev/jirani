import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',      // makes it accessible on the network
    port: 5173,
  },
  preview: {
    host: '0.0.0.0',      // same for production preview
    port: 4173,
  }
})
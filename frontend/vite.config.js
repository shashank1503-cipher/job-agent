import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/jobs': 'http://localhost:8000',
      '/applications': 'http://localhost:8000',
      '/runs': 'http://localhost:8000',
    },
  },
})

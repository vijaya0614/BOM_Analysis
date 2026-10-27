import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/risk': 'http://127.0.0.1:8001',
      '/components': 'http://127.0.0.1:8000',
      '/substitutes': 'http://127.0.0.1:8000',
    }
  }
})

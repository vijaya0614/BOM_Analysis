import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/risk': 'http://127.0.0.1:8000',
      '/components': 'http://127.0.0.1:8000',
      '/industry': 'http://127.0.0.1:8000',
      '/substitutes': 'http://127.0.0.1:8000',
      '/decision': 'http://127.0.0.1:8000',
      '/evidence': 'http://127.0.0.1:8000',
      '/risk-report': 'http://127.0.0.1:8000',
    }
  }
})

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server proxies /api to the backend so that requests are same-origin.
// The alternative is CORS middleware on FastAPI, which would mean shipping a
// permissive origin policy in the deployed app to solve a dev-only problem.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})

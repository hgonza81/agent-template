import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

import { parseApiBaseUrl } from './configuration.js'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  parseApiBaseUrl(env.VITE_API_BASE_URL)

  return {
    plugins: [react()],
  }
})

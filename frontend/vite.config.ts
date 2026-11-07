import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

import { parseApiBaseUrl, parseAuthConfig } from './configuration.js'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  parseApiBaseUrl(env.VITE_API_BASE_URL)
  parseAuthConfig({
    clientId: env.VITE_ENTRA_CLIENT_ID,
    authority: env.VITE_ENTRA_AUTHORITY,
    scopes: env.VITE_API_SCOPES,
  })

  return {
    plugins: [react()],
    test: {
      environment: 'jsdom',
      include: ['src/**/*.test.{ts,tsx}'],
    },
  }
})

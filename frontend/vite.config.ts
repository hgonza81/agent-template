import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

import { parseApiBaseUrl, parseAuthConfig, parseLocalSignInUrl } from './configuration.js'

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  parseApiBaseUrl(env.VITE_API_BASE_URL)
  parseAuthConfig({
    clientId: env.VITE_ENTRA_CLIENT_ID,
    authority: env.VITE_ENTRA_AUTHORITY,
    scopes: env.VITE_API_SCOPES,
  })

  // Throws for production builds, so the local sign-in cannot ship.
  parseLocalSignInUrl(env.VITE_LOCAL_SIGNIN_URL, command === 'serve' && mode !== 'production')

  return {
    plugins: [react()],
    test: {
      environment: 'jsdom',
      include: ['src/**/*.test.{ts,tsx}'],
    },
  }
})

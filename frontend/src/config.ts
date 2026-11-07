import { parseApiBaseUrl, parseAuthConfig } from '../configuration'

export const apiBaseUrl = parseApiBaseUrl(import.meta.env.VITE_API_BASE_URL)

export const authConfig = parseAuthConfig({
  clientId: import.meta.env.VITE_ENTRA_CLIENT_ID,
  authority: import.meta.env.VITE_ENTRA_AUTHORITY,
  scopes: import.meta.env.VITE_API_SCOPES,
})

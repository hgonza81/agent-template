import { parseApiBaseUrl, parseAuthConfig, parseLocalSignInUrl } from '../configuration'

export const apiBaseUrl = parseApiBaseUrl(import.meta.env.VITE_API_BASE_URL)

export const authConfig = parseAuthConfig({
  clientId: import.meta.env.VITE_ENTRA_CLIENT_ID,
  authority: import.meta.env.VITE_ENTRA_AUTHORITY,
  scopes: import.meta.env.VITE_API_SCOPES,
})

// Development server only: `import.meta.env.DEV` is false in production builds.
export const localSignInUrl = parseLocalSignInUrl(
  import.meta.env.VITE_LOCAL_SIGNIN_URL,
  import.meta.env.DEV,
)

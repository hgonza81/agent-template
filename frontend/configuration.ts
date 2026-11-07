export function parseApiBaseUrl(value: string | undefined): string {
  const configuredValue = value ?? 'http://127.0.0.1:8000'
  let url: URL

  try {
    url = new URL(configuredValue)
  } catch {
    throw new Error('VITE_API_BASE_URL must be an absolute HTTP(S) URL')
  }

  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username.length > 0 ||
    url.password.length > 0
  ) {
    throw new Error('VITE_API_BASE_URL must be an absolute HTTP(S) URL without credentials')
  }

  return url.toString().replace(/\/$/, '')
}

export interface AuthConfig {
  clientId: string
  authority: string
  scopes: string[]
}

export interface RawAuthConfig {
  clientId?: string | undefined
  authority?: string | undefined
  scopes?: string | undefined
}

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/**
 * Entra External ID values are pending provisioning. When none are set the app
 * runs with sign-in disabled (null); a partial configuration is an error.
 */
export function parseAuthConfig(raw: RawAuthConfig): AuthConfig | null {
  const clientId = raw.clientId?.trim() ?? ''
  const authority = raw.authority?.trim() ?? ''
  const scopes = (raw.scopes ?? '').split(/\s+/).filter((scope) => scope.length > 0)

  if (clientId === '' && authority === '' && scopes.length === 0) {
    return null
  }
  if (clientId === '' || authority === '' || scopes.length === 0) {
    throw new Error(
      'VITE_ENTRA_CLIENT_ID, VITE_ENTRA_AUTHORITY, and VITE_API_SCOPES must be set together',
    )
  }
  if (!GUID.test(clientId)) {
    throw new Error('VITE_ENTRA_CLIENT_ID must be an application (client) ID GUID')
  }

  let url: URL
  try {
    url = new URL(authority)
  } catch {
    throw new Error('VITE_ENTRA_AUTHORITY must be an absolute HTTPS URL')
  }
  if (
    url.protocol !== 'https:' ||
    url.username.length > 0 ||
    url.password.length > 0 ||
    url.search.length > 0 ||
    url.hash.length > 0
  ) {
    throw new Error(
      'VITE_ENTRA_AUTHORITY must be an HTTPS URL without credentials, query, or fragment',
    )
  }

  return { clientId, authority: url.toString().replace(/\/$/, ''), scopes }
}

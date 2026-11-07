export const DEFAULT_RETURN_PATH = '/chat'
const STORAGE_KEY = 'agent-template.return-path'

/** Accepts only same-origin, app-internal paths; anything else becomes the default. */
export function safeReturnPath(value: unknown): string {
  if (
    typeof value !== 'string' ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    value.includes('\\') ||
    // eslint-disable-next-line no-control-regex
    /[\u0000-\u001f\u007f]/.test(value) ||
    value === '/auth/callback' ||
    value.startsWith('/auth/callback?') ||
    value.startsWith('/auth/callback/')
  ) {
    return DEFAULT_RETURN_PATH
  }
  return value
}

// The return path is a route, not a credential; tokens stay in MSAL's cache.
export function saveReturnPath(path: string): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, safeReturnPath(path))
  } catch {
    // Storage may be unavailable; fall back to the default route.
  }
}

export function readReturnPath(): string {
  try {
    return safeReturnPath(sessionStorage.getItem(STORAGE_KEY))
  } catch {
    return DEFAULT_RETURN_PATH
  }
}

export function clearReturnPath(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // Nothing to clear.
  }
}

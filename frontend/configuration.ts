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

import { describe, expect, it } from 'vitest'

import { parseApiBaseUrl } from '../configuration'

describe('parseApiBaseUrl', () => {
  it('uses the local API URL when no value is configured', () => {
    expect(parseApiBaseUrl(undefined)).toBe('http://127.0.0.1:8000')
  })

  it('rejects invalid URLs and URLs containing credentials', () => {
    expect(() => parseApiBaseUrl('not-a-url')).toThrow(
      'VITE_API_BASE_URL must be an absolute HTTP(S) URL',
    )
    expect(() => parseApiBaseUrl('https://user:pass@example.test')).toThrow(
      'VITE_API_BASE_URL must be an absolute HTTP(S) URL without credentials',
    )
  })
})

import { describe, expect, it } from 'vitest'

import { parseApiBaseUrl, parseAuthConfig, parseLocalSignInUrl } from '../configuration'

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

describe('parseAuthConfig', () => {
  const valid = {
    clientId: '11111111-2222-3333-4444-555555555555',
    authority: 'https://tenant.ciamlogin.com/tenant-id/',
    scopes: 'api://abc/chat.use',
  }

  it('is disabled when nothing is configured', () => {
    expect(parseAuthConfig({})).toBeNull()
    expect(parseAuthConfig({ clientId: '', authority: ' ', scopes: '' })).toBeNull()
  })

  it('normalizes a complete configuration', () => {
    expect(parseAuthConfig({ ...valid, scopes: ' api://abc/chat.use  openid ' })).toEqual({
      clientId: valid.clientId,
      authority: 'https://tenant.ciamlogin.com/tenant-id',
      scopes: ['api://abc/chat.use', 'openid'],
    })
  })

  it('rejects partial configuration', () => {
    expect(() => parseAuthConfig({ clientId: valid.clientId })).toThrow('must be set together')
  })

  it('rejects invalid client IDs and authorities', () => {
    expect(() => parseAuthConfig({ ...valid, clientId: 'nope' })).toThrow('GUID')
    expect(() => parseAuthConfig({ ...valid, authority: 'not a url' })).toThrow('HTTPS URL')
    expect(() => parseAuthConfig({ ...valid, authority: 'http://tenant.example.test' })).toThrow(
      'HTTPS',
    )
    expect(() => parseAuthConfig({ ...valid, authority: 'https://u:p@tenant.example.test' })).toThrow(
      'HTTPS',
    )
    expect(() => parseAuthConfig({ ...valid, authority: 'https://t.example.test/?a=1' })).toThrow(
      'HTTPS',
    )
  })
})

describe('parseLocalSignInUrl', () => {
  it('is disabled when blank', () => {
    expect(parseLocalSignInUrl(undefined, true)).toBeNull()
    expect(parseLocalSignInUrl('  ', false)).toBeNull()
  })

  it('accepts a loopback HTTP URL on the dev server', () => {
    expect(parseLocalSignInUrl('http://127.0.0.1:9000/', true)).toBe('http://127.0.0.1:9000')
  })

  it('is refused outside the dev server', () => {
    expect(() => parseLocalSignInUrl('http://127.0.0.1:9000', false)).toThrow(
      'only allowed on the development server',
    )
  })

  it('rejects non-loopback, HTTPS, credentialed, and malformed URLs', () => {
    for (const value of [
      'http://example.test:9000',
      'https://127.0.0.1:9000',
      'http://user:pw@127.0.0.1:9000',
      'http://127.0.0.1:9000?x=1',
      'nope',
    ]) {
      expect(() => parseLocalSignInUrl(value, true)).toThrow('loopback HTTP URL')
    }
  })
})

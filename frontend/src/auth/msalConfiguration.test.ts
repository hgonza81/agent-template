import { describe, expect, it } from 'vitest'

import { createMsalConfiguration } from './msalConfiguration'

describe('createMsalConfiguration', () => {
  const config = createMsalConfiguration(
    {
      clientId: '11111111-2222-3333-4444-555555555555',
      authority: 'https://tenant.ciamlogin.com/tenant-id',
      scopes: ['api://abc/chat.use'],
    },
    'http://127.0.0.1:5173',
  )

  it('configures a public client with no secret', () => {
    expect(JSON.stringify(config).toLowerCase()).not.toContain('secret')
    expect(config.auth.clientId).toBe('11111111-2222-3333-4444-555555555555')
    expect(config.auth.knownAuthorities).toEqual(['tenant.ciamlogin.com'])
  })

  it('uses the callback and logout URIs and session-scoped token storage', () => {
    expect(config.auth.redirectUri).toBe('http://127.0.0.1:5173/auth/callback')
    expect(config.auth.postLogoutRedirectUri).toBe('http://127.0.0.1:5173/')
    expect(config.cache?.cacheLocation).toBe('sessionStorage')
  })
})

import { InteractionRequiredAuthError, InteractionStatus } from '@azure/msal-browser'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useAuth } from './AuthContext'
import { MsalAuthProvider } from './MsalAuthProvider'

const msal = vi.hoisted(() => ({
  instance: {
    loginRedirect: vi.fn(),
    logoutRedirect: vi.fn(),
    acquireTokenSilent: vi.fn(),
    acquireTokenRedirect: vi.fn(),
  },
  accounts: [] as { name: string; username?: string }[],
  inProgress: 'none',
}))

vi.mock('@azure/msal-react', () => ({
  MsalProvider: ({ children }: { children: React.ReactNode }) => children,
  useMsal: () => msal,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  msal.accounts = []
  msal.inProgress = InteractionStatus.None
  sessionStorage.clear()
})

const config = {
  clientId: '11111111-2222-3333-4444-555555555555',
  authority: 'https://tenant.ciamlogin.com/tenant-id',
  scopes: ['api://abc/chat.use'],
}

function setup() {
  const captured: { auth?: ReturnType<typeof useAuth> } = {}
  function Probe() {
    const auth = useAuth()
    useEffect(() => {
      captured.auth = auth
    })
    return <p>{auth.status}</p>
  }
  render(
    <MsalAuthProvider client={msal.instance as never} config={config}>
      <Probe />
    </MsalAuthProvider>,
  )
  return captured.auth!
}

describe('MsalAuthProvider', () => {
  it('maps MSAL state to auth status', () => {
    setup()
    expect(screen.getByText('unauthenticated')).toBeDefined()
    cleanup()

    msal.inProgress = InteractionStatus.HandleRedirect
    setup()
    expect(screen.getByText('loading')).toBeDefined()
    cleanup()

    msal.inProgress = InteractionStatus.None
    msal.accounts = [{ name: 'Ada' }]
    const auth = setup()
    expect(screen.getByText('authenticated')).toBeDefined()
    expect(auth.displayName).toBe('Ada')
  })

  it.each([['unknown'], ['Unknown'], ['  '], ['']])(
    'shows the email when the name is the placeholder %j',
    (name) => {
      msal.inProgress = InteractionStatus.None
      msal.accounts = [{ name, username: 'ada@example.test' }]
      const auth = setup()
      expect(screen.getByText('authenticated')).toBeDefined()
      expect(auth.displayName).toBe('ada@example.test')
    },
  )

  it('shows nothing when there is neither a real name nor an email', () => {
    msal.inProgress = InteractionStatus.None
    msal.accounts = [{ name: 'unknown' }]
    const auth = setup()
    expect(auth.displayName).toBeNull()
  })

  it('prefers a real name over the email', () => {
    msal.inProgress = InteractionStatus.None
    msal.accounts = [{ name: 'Ada', username: 'ada@example.test' }]
    const auth = setup()
    expect(auth.displayName).toBe('Ada')
  })

  it('signs in with the API scope via redirect and remembers the route', async () => {
    const auth = setup()
    await auth.signIn('/chat')

    expect(msal.instance.loginRedirect).toHaveBeenCalledWith({
      scopes: config.scopes,
      redirectUri: `${window.location.origin}/auth/callback`,
    })
    expect(sessionStorage.getItem('agent-template.return-path')).toBe('/chat')
  })

  it('signs up using the create prompt', async () => {
    const auth = setup()
    await auth.signUp('/chat')

    expect(msal.instance.loginRedirect).toHaveBeenCalledWith(
      expect.objectContaining({ prompt: 'create', scopes: config.scopes }),
    )
  })

  it('acquires access tokens silently and falls back to redirect when interaction is required', async () => {
    msal.accounts = [{ name: 'Ada' }]
    const auth = setup()

    msal.instance.acquireTokenSilent.mockResolvedValueOnce({ accessToken: 'abc' })
    await expect(auth.getAccessToken()).resolves.toBe('abc')

    msal.instance.acquireTokenSilent.mockRejectedValueOnce(
      new InteractionRequiredAuthError('interaction_required', 'Interaction required'),
    )
    msal.instance.acquireTokenRedirect.mockResolvedValueOnce(undefined)
    await expect(auth.getAccessToken()).rejects.toBeInstanceOf(InteractionRequiredAuthError)
    await waitFor(() => {
      expect(msal.instance.acquireTokenRedirect).toHaveBeenCalled()
    })
  })

  it('refuses to fetch a token when signed out', async () => {
    const auth = setup()
    await expect(auth.getAccessToken()).rejects.toThrow('Not signed in')
  })
})

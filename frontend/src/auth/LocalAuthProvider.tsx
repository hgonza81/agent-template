import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'

import { AuthContext, type AuthState } from './AuthContext'
import { saveReturnPath } from './returnPath'

/**
 * Opt-in development sign-in (no Azure). It obtains a real signed token from
 * the loopback issuer script, so the API still validates it. Selected in
 * main.tsx only on the dev server when VITE_LOCAL_SIGNIN_URL is set.
 */
const STORAGE_KEY = 'agent-template.local-session'

interface Session {
  accessToken: string
  name: string
  expiresAt: number
}

function readSession(): Session | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (raw === null) {
      return null
    }
    const value: unknown = JSON.parse(raw)
    if (
      typeof value === 'object' &&
      value !== null &&
      'accessToken' in value &&
      typeof value.accessToken === 'string' &&
      'name' in value &&
      typeof value.name === 'string' &&
      'expiresAt' in value &&
      typeof value.expiresAt === 'number' &&
      value.expiresAt > Date.now()
    ) {
      return { accessToken: value.accessToken, name: value.name, expiresAt: value.expiresAt }
    }
  } catch {
    // Fall through to signed out.
  }
  return null
}

async function requestLocalSession(issuerUrl: string): Promise<Session> {
  const response = await fetch(`${issuerUrl}/token`)
  if (!response.ok) {
    throw new Error('The local issuer rejected the sign-in request')
  }
  const body: unknown = await response.json()
  if (
    typeof body !== 'object' ||
    body === null ||
    !('access_token' in body) ||
    typeof body.access_token !== 'string' ||
    !('name' in body) ||
    typeof body.name !== 'string' ||
    !('expires_in' in body) ||
    typeof body.expires_in !== 'number'
  ) {
    throw new Error('The local issuer returned an unexpected response')
  }
  // Renew a minute early so a token is never used right at expiry.
  return {
    accessToken: body.access_token,
    name: body.name,
    expiresAt: Date.now() + body.expires_in * 1000 - 60_000,
  }
}

export function LocalAuthProvider({
  issuerUrl,
  children,
}: {
  issuerUrl: string
  children: ReactNode
}) {
  const [session, setSession] = useState<Session | null>(readSession)
  const navigate = useNavigate()

  const signIn = useCallback(
    async (returnTo?: string) => {
      saveReturnPath(returnTo ?? '/')
      const next = await requestLocalSession(issuerUrl)
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      setSession(next)
      void navigate('/auth/callback')
    },
    [issuerUrl, navigate],
  )

  const value = useMemo<AuthState>(
    () => ({
      status: session === null ? 'unauthenticated' : 'authenticated',
      displayName: session?.name ?? null,
      signIn,
      signUp: signIn,
      signOut: () => {
        window.sessionStorage.removeItem(STORAGE_KEY)
        setSession(null)
        void navigate('/')
        return Promise.resolve()
      },
      getAccessToken: async () => {
        if (session === null) {
          throw new Error('Not signed in')
        }
        if (session.expiresAt > Date.now()) {
          return session.accessToken
        }
        const next = await requestLocalSession(issuerUrl)
        window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
        setSession(next)
        return next.accessToken
      },
    }),
    [issuerUrl, navigate, session, signIn],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

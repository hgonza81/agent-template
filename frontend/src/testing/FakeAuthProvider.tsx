import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'

import { AuthContext, type AuthState } from '../auth/AuthContext'
import { saveReturnPath } from '../auth/returnPath'

/**
 * Safe local test identity: an in-memory sign-in that mimics the MSAL redirect
 * round trip (sign-in -> callback route -> authenticated) with a fake token.
 * It uses no real tenant, credentials, or network, and ships only in tests.
 */
export const FAKE_ACCESS_TOKEN = 'fake-access-token-for-tests'

export function FakeAuthProvider({ children }: { children: ReactNode }) {
  const [signedIn, setSignedIn] = useState(false)
  const navigate = useNavigate()

  const value = useMemo<AuthState>(
    () => ({
      status: signedIn ? 'authenticated' : 'unauthenticated',
      displayName: signedIn ? 'Test User' : null,
      signIn: (returnTo) => {
        saveReturnPath(returnTo ?? '/')
        setSignedIn(true)
        void navigate('/auth/callback')
        return Promise.resolve()
      },
      signUp: (returnTo) => {
        saveReturnPath(returnTo ?? '/')
        setSignedIn(true)
        void navigate('/auth/callback')
        return Promise.resolve()
      },
      signOut: () => {
        setSignedIn(false)
        void navigate('/')
        return Promise.resolve()
      },
      getAccessToken: () => Promise.resolve(FAKE_ACCESS_TOKEN),
    }),
    [navigate, signedIn],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

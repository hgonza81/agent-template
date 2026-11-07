import type { ReactNode } from 'react'

import { AuthContext, type AuthState } from './AuthContext'

const unavailable = (): Promise<never> =>
  Promise.reject(new Error('Authentication is not configured'))

const state: AuthState = {
  status: 'unconfigured',
  displayName: null,
  signIn: unavailable,
  signUp: unavailable,
  signOut: unavailable,
  getAccessToken: unavailable,
}

export function UnconfiguredAuthProvider({ children }: { children: ReactNode }) {
  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>
}

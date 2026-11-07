import { createContext, useContext } from 'react'

export type AuthStatus = 'unconfigured' | 'loading' | 'authenticated' | 'unauthenticated'

export interface AuthState {
  status: AuthStatus
  displayName: string | null
  signIn: (returnTo?: string) => Promise<void>
  signUp: (returnTo?: string) => Promise<void>
  signOut: () => Promise<void>
  getAccessToken: () => Promise<string>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const state = useContext(AuthContext)
  if (state === null) {
    throw new Error('useAuth must be used inside an AuthContext provider')
  }
  return state
}

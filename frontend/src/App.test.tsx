import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { AuthContext, type AuthState, type AuthStatus } from './auth/AuthContext'
import { saveReturnPath } from './auth/returnPath'

afterEach(() => {
  cleanup()
  sessionStorage.clear()
})

function renderApp(
  status: AuthStatus,
  initialEntry: string | { pathname: string; state?: unknown } = '/',
  overrides: Partial<AuthState> = {},
) {
  const state: AuthState = {
    status,
    displayName: status === 'authenticated' ? 'Ada Lovelace' : null,
    signIn: vi.fn(() => Promise.resolve()),
    signUp: vi.fn(() => Promise.resolve()),
    signOut: vi.fn(() => Promise.resolve()),
    getAccessToken: vi.fn(() => Promise.resolve('token')),
    ...overrides,
  }
  const wrap = (children: ReactNode) => (
    <AuthContext.Provider value={state}>
      <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
    </AuthContext.Provider>
  )
  render(wrap(<App />))
  return state
}

describe('App', () => {
  it('renders the shell and API documentation link', () => {
    renderApp('unauthenticated')

    expect(screen.getByRole('heading', { name: 'Agent Template' })).toBeDefined()
    expect(screen.getByRole('link', { name: 'API documentation' }).getAttribute('href')).toBe(
      'http://127.0.0.1:8000/docs',
    )
  })

  it('disables sign-in and explains why when auth is not configured', () => {
    renderApp('unconfigured')

    expect(screen.getByText(/not configured/)).toBeDefined()
    expect(screen.getByRole('button', { name: 'Sign in' }).hasAttribute('disabled')).toBe(true)
  })

  it('starts sign-in and sign-up from the start page', () => {
    const state = renderApp('unauthenticated')

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(state.signIn).toHaveBeenCalledWith('/chat')
    expect(state.signUp).toHaveBeenCalledWith('/chat')
  })

  it('shows a recoverable error when sign-in cannot start', async () => {
    renderApp('unauthenticated', '/', {
      signIn: vi.fn(() => Promise.reject(new Error('boom'))),
    })

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect((await screen.findByRole('alert')).textContent).toContain('could not start sign-in')
  })
})

describe('protected route', () => {
  it('sends unauthenticated visitors to the start page and remembers the destination', () => {
    const state = renderApp('unauthenticated', '/chat')

    expect(screen.queryByRole('heading', { name: 'Chat' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(state.signIn).toHaveBeenCalledWith('/chat')
  })

  it('never passes an unsafe remembered destination to sign-in', () => {
    const state = renderApp('unauthenticated', {
      pathname: '/',
      state: { from: '//evil.example.test' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(state.signIn).toHaveBeenCalledWith('/chat')
  })

  it('does not decide while the session is loading', () => {
    renderApp('loading', '/chat')

    expect(screen.getByRole('progressbar', { name: 'Checking your session' })).toBeDefined()
    expect(screen.queryByRole('button', { name: 'Sign in' })).toBeNull()
  })

  it('shows the chat page and sign-out to authenticated users', () => {
    const state = renderApp('authenticated', '/chat')

    expect(screen.getByRole('heading', { name: 'Chat' })).toBeDefined()
    expect(screen.getByText('Ada Lovelace')).toBeDefined()
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(state.signOut).toHaveBeenCalled()
  })
})

describe('callback page', () => {
  it('shows progress while MSAL completes the redirect', () => {
    renderApp('loading', '/auth/callback')

    expect(screen.getByRole('progressbar', { name: 'Completing sign-in' })).toBeDefined()
  })

  it('returns authenticated users to the remembered route', () => {
    saveReturnPath('/chat')
    renderApp('authenticated', '/auth/callback')

    expect(screen.getByRole('heading', { name: 'Chat' })).toBeDefined()
    expect(sessionStorage.getItem('agent-template.return-path')).toBeNull()
  })

  it('offers a way back when sign-in was cancelled or failed', () => {
    renderApp('unauthenticated', '/auth/callback')

    expect(screen.getByRole('alert').textContent).toContain('not completed')
    expect(screen.getByRole('link', { name: 'Back to the start page' })).toBeDefined()
  })
})

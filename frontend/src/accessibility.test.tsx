import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { AuthContext, type AuthState, type AuthStatus } from './auth/AuthContext'
import { FakeAuthProvider } from './testing/FakeAuthProvider'

const subscription = { id: 's', started_at: '2026-01-01T00:00:00Z', email: 'a@example.test' }
const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

function renderWithStatus(status: AuthStatus, path: string) {
  const state: AuthState = {
    status,
    displayName: null,
    signIn: vi.fn(() => Promise.resolve()),
    signUp: vi.fn(() => Promise.resolve()),
    signOut: vi.fn(() => Promise.resolve()),
    getAccessToken: vi.fn(() => Promise.resolve('token')),
  }
  render(
    <AuthContext.Provider value={state}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

function expectNamedControls() {
  for (const control of [...screen.queryAllByRole('button'), ...screen.queryAllByRole('link')]) {
    const name = control.getAttribute('aria-label') ?? control.textContent ?? ''
    expect(name.trim()).not.toBe('')
  }
  const ids = [...document.querySelectorAll('[id]')].map((element) => element.id)
  expect(new Set(ids).size).toBe(ids.length)
}

describe('accessibility of every sign-in state', () => {
  it.each<AuthStatus>(['unconfigured', 'loading', 'unauthenticated', 'authenticated'])(
    'has one main landmark, one h1, named controls, and unique ids when %s',
    (status) => {
      fetchMock.mockResolvedValue(Response.json(subscription))
      renderWithStatus(status, '/')

      expect(screen.getAllByRole('main')).toHaveLength(1)
      expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
      expectNamedControls()
    },
  )

  it('keeps the loading and callback progress indicators labelled', () => {
    renderWithStatus('loading', '/chat')
    expect(screen.getByRole('progressbar', { name: 'Checking your session' })).toBeDefined()
    cleanup()
    renderWithStatus('loading', '/auth/callback')
    expect(screen.getByRole('progressbar', { name: 'Completing sign-in' })).toBeDefined()
  })

  it('moves unknown routes to the start page with a way to sign in', () => {
    renderWithStatus('unauthenticated', '/does-not-exist')

    expect(screen.getByRole('heading', { level: 2, name: 'Get started' })).toBeDefined()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDefined()
  })

  it('offers authenticated users a link from the start page to the chat', () => {
    fetchMock.mockResolvedValue(Response.json(subscription))
    renderWithStatus('authenticated', '/')

    expect(screen.getByRole('link', { name: 'Open chat' }).getAttribute('href')).toBe('/chat')
  })
})

describe('protected chat accessibility and recovery', () => {
  async function openChat() {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <FakeAuthProvider>
          <App />
        </FakeAuthProvider>
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    return screen.findByRole('log', { name: 'Conversation' })
  }

  it('labels the conversation log, message field, and send button', async () => {
    fetchMock.mockResolvedValue(Response.json(subscription))
    const log = await openChat()

    expect(log.getAttribute('aria-live')).toBe('polite')
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeDefined()
    expect(screen.getByRole('button', { name: 'Send' }).hasAttribute('disabled')).toBe(true)
    expectNamedControls()
  })

  it.each([
    [429, 'too quickly'],
    [422, 'too long or empty'],
    [504, 'took too long'],
    [500, 'could not be sent'],
  ])('announces a %i chat failure, restores the text, and allows resending', async (status, text) => {
    fetchMock.mockImplementation((url) =>
      Promise.resolve(
        String(url).endsWith('/me/subscription')
          ? Response.json(subscription)
          : new Response(null, { status }),
      ),
    )
    await openChat()
    const field = screen.getByRole<HTMLTextAreaElement>('textbox', { name: 'Message' })

    fireEvent.change(field, { target: { value: 'hello' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText(new RegExp(text))).toBeDefined()
    expect(field.value).toBe('hello')
    expect(screen.getByRole('button', { name: 'Send' }).hasAttribute('disabled')).toBe(false)
  })

  it('recovers from a failed session check and signs out from the start page', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 401 }))
    await openChat().catch(() => undefined)

    expect(await screen.findByRole('alert')).toBeDefined()
    expect(screen.queryByRole('log')).toBeNull()
    expectNamedControls()
  })
})

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { SubscriptionResponse } from './generated/Api'
import { FAKE_ACCESS_TOKEN, FakeAuthProvider } from './testing/FakeAuthProvider'

const subscription: SubscriptionResponse = {
  id: '6f1c0f66-0000-4000-8000-000000000001',
  started_at: '2026-01-01T00:00:00Z',
  email: 'test.user@example.test',
}

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

function renderFlow(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <FakeAuthProvider>
        <App />
      </FakeAuthProvider>
    </MemoryRouter>,
  )
}

describe('sign-in to provisioned chat flow', () => {
  it('returns a visitor to the protected chat after sign-in and provisions the account', async () => {
    fetchMock.mockResolvedValue(Response.json(subscription))
    renderFlow('/chat')

    // Protected route sends the visitor to the start page.
    expect(screen.queryByRole('heading', { name: 'Chat' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Chat' })).toBeDefined()
    expect(screen.getByText('Signed in as test.user@example.test')).toBeDefined()
    expect(screen.getByText('Test User')).toBeDefined()

    // Provisioning is a bearer-authenticated GET with no body or identity input.
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('http://127.0.0.1:8000/api/v1/me/subscription')
    expect(init?.method).toBeUndefined()
    expect(init?.body).toBeUndefined()
    expect(init?.headers).toEqual({ Authorization: `Bearer ${FAKE_ACCESS_TOKEN}` })
  })

  it('works for new accounts created from the start page', async () => {
    fetchMock.mockResolvedValue(Response.json(subscription))
    renderFlow('/')

    fireEvent.click(screen.getByRole('button', { name: 'Create a free account' }))

    expect(await screen.findByRole('heading', { name: 'Chat' })).toBeDefined()
  })

  it('shows progress while the account is being set up', async () => {
    fetchMock.mockReturnValue(new Promise(() => undefined))
    renderFlow('/')

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('progressbar', { name: 'Setting up your account' })).toBeDefined()
  })

  it('recovers from a provisioning failure with retry', async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(Response.json(subscription))
    renderFlow('/')

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect((await screen.findByRole('alert')).textContent).toContain('could not set up')

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('heading', { name: 'Chat' })).toBeDefined()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('offers sign-out when the API rejects the session', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 403 }))
    renderFlow('/')

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect((await screen.findByRole('alert')).textContent).toContain('cannot access')
    expect(screen.queryByRole('heading', { name: 'Chat' })).toBeNull()

    fireEvent.click(screen.getAllByRole('button', { name: 'Sign out' })[0]!)

    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeDefined()
  })

  it('signs out back to the start page and protects the chat again', async () => {
    fetchMock.mockResolvedValue(Response.json(subscription))
    renderFlow('/chat')
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByRole('heading', { name: 'Chat' })

    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeDefined()
    expect(screen.queryByRole('heading', { name: 'Chat' })).toBeNull()
  })
})

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { FAKE_ACCESS_TOKEN, FakeAuthProvider } from './testing/FakeAuthProvider'

const fetchMock = vi.fn<typeof fetch>()
const subscription = { id: 's', started_at: '2026-01-01T00:00:00Z', email: null }

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation((url) =>
    Promise.resolve(
      String(url).endsWith('/me/subscription')
        ? Response.json(subscription)
        : Response.json({ reply: 'Fake reply 1: hello' }),
    ),
  )
})

afterEach(() => {
  cleanup()
  fetchMock.mockReset()
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

async function openChat() {
  render(
    <MemoryRouter initialEntries={['/chat']}>
      <FakeAuthProvider>
        <App />
      </FakeAuthProvider>
    </MemoryRouter>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  await screen.findByRole('log', { name: 'Conversation' })
}

describe('chat screen', () => {
  it('sends a message with only the message text and shows the reply', async () => {
    await openChat()

    fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), {
      target: { value: 'hello' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Fake reply 1: hello')).toBeDefined()
    expect(screen.getByText('hello')).toBeDefined()
    const [url, init] = fetchMock.mock.calls.at(-1)!
    expect(url).toBe('http://127.0.0.1:8000/api/v1/chat/messages')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init?.body as string)).toEqual({ message: 'hello' })
    expect(init?.headers).toMatchObject({ Authorization: `Bearer ${FAKE_ACCESS_TOKEN}` })
  })

  it('does not send empty messages', async () => {
    await openChat()

    expect(screen.getByRole('button', { name: 'Send' }).hasAttribute('disabled')).toBe(true)
  })

  it('shows a status while waiting and disables input', async () => {
    await openChat()
    fetchMock.mockReturnValue(new Promise(() => undefined))

    fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), {
      target: { value: 'hello' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect((await screen.findByRole('status')).textContent).toContain('replying')
    expect(screen.getByRole('textbox', { name: 'Message' }).hasAttribute('disabled')).toBe(true)
  })

  it('restores the text and offers retry when sending fails', async () => {
    await openChat()
    fetchMock.mockResolvedValue(new Response(null, { status: 503 }))

    fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), {
      target: { value: 'hello' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect((await screen.findByRole('alert')).textContent).toContain('could not be sent')
    await waitFor(() => {
      expect((screen.getByRole('textbox', { name: 'Message' }) as HTMLTextAreaElement).value).toBe(
        'hello',
      )
    })
  })
})

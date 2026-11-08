import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useAuth } from './AuthContext'
import { LocalAuthProvider } from './LocalAuthProvider'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

function setup() {
  const captured: { auth?: ReturnType<typeof useAuth> } = {}
  function Probe() {
    captured.auth = useAuth()
    return <p>{captured.auth.status}</p>
  }
  render(
    <MemoryRouter>
      <LocalAuthProvider issuerUrl="http://127.0.0.1:9000">
        <Probe />
      </LocalAuthProvider>
    </MemoryRouter>,
  )
  return captured
}

function stubIssuer(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const tokenResponse = () =>
  Response.json({ access_token: 'signed.jwt.value', name: 'Local Developer', expires_in: 3600 })

describe('LocalAuthProvider', () => {
  it('starts signed out', () => {
    setup()
    expect(screen.getByText('unauthenticated')).toBeTruthy()
  })

  it('signs in with a token from the loopback issuer', async () => {
    const fetchMock = stubIssuer(tokenResponse())
    const captured = setup()

    await captured.auth?.signIn('/chat')

    await waitFor(() => {
      expect(screen.getByText('authenticated')).toBeTruthy()
    })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:9000/token')
    expect(captured.auth?.displayName).toBe('Local Developer')
    await expect(captured.auth?.getAccessToken()).resolves.toBe('signed.jwt.value')
  })

  it('stays signed out when the issuer rejects the request', async () => {
    stubIssuer(new Response('{}', { status: 403 }))
    const captured = setup()

    await expect(captured.auth?.signIn()).rejects.toThrow('rejected')
    expect(screen.getByText('unauthenticated')).toBeTruthy()
  })

  it('rejects malformed issuer responses', async () => {
    stubIssuer(Response.json({ access_token: 1 }))
    const captured = setup()

    await expect(captured.auth?.signIn()).rejects.toThrow('unexpected response')
  })

  it('signs out and refuses to hand out a token', async () => {
    stubIssuer(tokenResponse())
    const captured = setup()
    await captured.auth?.signIn()
    await waitFor(() => {
      expect(screen.getByText('authenticated')).toBeTruthy()
    })

    await captured.auth?.signOut()

    await waitFor(() => {
      expect(screen.getByText('unauthenticated')).toBeTruthy()
    })
    await expect(captured.auth?.getAccessToken()).rejects.toThrow('Not signed in')
  })
})

import { afterEach, describe, expect, it } from 'vitest'

import {
  clearReturnPath,
  DEFAULT_RETURN_PATH,
  readReturnPath,
  safeReturnPath,
  saveReturnPath,
} from './returnPath'

afterEach(() => {
  sessionStorage.clear()
})

describe('safeReturnPath', () => {
  it('keeps app-internal paths', () => {
    expect(safeReturnPath('/chat')).toBe('/chat')
    expect(safeReturnPath('/chat?x=1#top')).toBe('/chat?x=1#top')
  })

  it.each([
    'https://evil.example.test',
    '//evil.example.test',
    '/\\evil.example.test',
    'chat',
    '/chat\nSet-Cookie: x',
    '/auth/callback',
    '/auth/callback?code=1',
    null,
    undefined,
    42,
  ])('rejects %j', (value) => {
    expect(safeReturnPath(value)).toBe(DEFAULT_RETURN_PATH)
  })
})

describe('stored return path', () => {
  it('round-trips and clears', () => {
    saveReturnPath('/chat?x=1')
    expect(readReturnPath()).toBe('/chat?x=1')
    clearReturnPath()
    expect(readReturnPath()).toBe(DEFAULT_RETURN_PATH)
  })

  it('sanitizes tampered storage', () => {
    sessionStorage.setItem('agent-template.return-path', '//evil.example.test')
    expect(readReturnPath()).toBe(DEFAULT_RETURN_PATH)
  })
})

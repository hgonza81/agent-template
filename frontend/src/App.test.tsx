import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import App from './App'

afterEach(cleanup)

describe('App', () => {
  it('renders the application shell and API documentation link', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Agent Template' })).toBeDefined()
    expect(screen.getByRole('link', { name: 'API documentation' }).getAttribute('href'))
      .toBe('http://127.0.0.1:8000/docs')
  })
})

import { Alert, Button, Link, Stack, Typography } from '@mui/material'
import { useState } from 'react'
import { Link as RouterLink, useLocation } from 'react-router'

import { apiBaseUrl } from '../config'
import { useAuth } from '../auth/AuthContext'
import { safeReturnPath } from '../auth/returnPath'

export function HomePage() {
  const { status, signIn, signUp } = useAuth()
  const location = useLocation()
  const [failed, setFailed] = useState(false)
  const from = (location.state as { from?: unknown } | null)?.from
  const returnTo = safeReturnPath(from)

  const start = (action: (returnTo: string) => Promise<void>) => {
    setFailed(false)
    action(returnTo).catch(() => {
      setFailed(true)
    })
  }

  return (
    <Stack spacing={2}>
      <Typography color="text.secondary">
        Sign in or create a free account to chat with the agent.
      </Typography>
      {status === 'unconfigured' && (
        <Alert severity="info">
          Sign-in is not configured for this environment yet.
        </Alert>
      )}
      {failed && (
        <Alert severity="error" role="alert">
          We could not start sign-in. Please try again.
        </Alert>
      )}
      {status === 'authenticated' ? (
        <Button component={RouterLink} to="/chat" variant="contained" sx={{ alignSelf: 'flex-start' }}>
          Open chat
        </Button>
      ) : (
        <Stack direction="row" spacing={2}>
          <Button
            variant="contained"
            disabled={status !== 'unauthenticated'}
            onClick={() => {
              start(signIn)
            }}
          >
            Sign in
          </Button>
          <Button
            variant="outlined"
            disabled={status !== 'unauthenticated'}
            onClick={() => {
              start(signUp)
            }}
          >
            Create account
          </Button>
        </Stack>
      )}
      <Link href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer">
        API documentation
      </Link>
    </Stack>
  )
}

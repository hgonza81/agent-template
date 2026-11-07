import { Alert, Button, Link, Stack, Typography } from '@mui/material'
import { useState } from 'react'
import { Link as RouterLink, useLocation } from 'react-router'

import { useAuth } from '../auth/AuthContext'
import { safeReturnPath } from '../auth/returnPath'
import { apiBaseUrl } from '../config'

export function HomePage() {
  const { status, signIn, signUp } = useAuth()
  const location = useLocation()
  const [failed, setFailed] = useState(false)
  const from = (location.state as { from?: unknown } | null)?.from
  const returnTo = safeReturnPath(from)
  const ready = status === 'unauthenticated'

  const start = (action: (returnTo: string) => Promise<void>) => {
    setFailed(false)
    action(returnTo).catch(() => {
      setFailed(true)
    })
  }

  return (
    <Stack spacing={3}>
      <Typography component="h2" variant="h5">
        {status === 'authenticated' ? 'Welcome back' : 'Get started'}
      </Typography>
      {status === 'unconfigured' && (
        <Alert severity="info">Sign-in is not configured for this environment yet.</Alert>
      )}
      {failed && (
        <Alert severity="error" role="alert">
          We could not start sign-in. Please try again.
        </Alert>
      )}
      {status === 'authenticated' ? (
        <Button
          component={RouterLink}
          to="/chat"
          variant="contained"
          sx={{ alignSelf: 'flex-start' }}
        >
          Open chat
        </Button>
      ) : (
        <Stack component="section" aria-labelledby="account-heading" spacing={2}>
          <Typography id="account-heading" component="h3" variant="h6">
            Your account
          </Typography>
          <Typography color="text.secondary">
            Accounts are free. Registration, email verification, and sign-in happen on
            Microsoft&apos;s secure page. This app never sees your password.
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <Button
              variant="contained"
              disabled={!ready}
              onClick={() => {
                start(signUp)
              }}
            >
              Create a free account
            </Button>
            <Button
              variant="outlined"
              disabled={!ready}
              onClick={() => {
                start(signIn)
              }}
            >
              Sign in
            </Button>
          </Stack>
          <Typography variant="body2" color="text.secondary">
            Forgot your password?{' '}
            <Link
              component="button"
              type="button"
              disabled={!ready}
              aria-describedby="reset-help"
              onClick={() => {
                start(signIn)
              }}
            >
              Reset it on the sign-in page
            </Link>
            <span id="reset-help" style={{ display: 'block' }}>
              Choose the password reset option on the Microsoft sign-in page. The reset is handled
              entirely by Microsoft.
            </span>
          </Typography>
        </Stack>
      )}
      <Link href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer">
        API documentation
      </Link>
    </Stack>
  )
}

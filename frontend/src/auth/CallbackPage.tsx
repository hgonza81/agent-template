import { Alert, CircularProgress, Link, Stack } from '@mui/material'
import { useEffect } from 'react'
import { Link as RouterLink, Navigate } from 'react-router'

import { useAuth } from './AuthContext'
import { clearReturnPath, readReturnPath } from './returnPath'

export function CallbackPage() {
  const { status } = useAuth()
  const authenticated = status === 'authenticated'

  useEffect(() => {
    if (authenticated) {
      clearReturnPath()
    }
  }, [authenticated])

  if (authenticated) {
    return <Navigate to={readReturnPath()} replace />
  }
  if (status === 'loading') {
    return (
      <Stack sx={{ alignItems: 'center', py: 8 }}>
        <CircularProgress aria-label="Completing sign-in" />
      </Stack>
    )
  }
  return (
    <Stack spacing={2} sx={{ py: 4 }}>
      <Alert severity="warning" role="alert">
        Sign-in was not completed.
      </Alert>
      <Link component={RouterLink} to="/">
        Back to the start page
      </Link>
    </Stack>
  )
}

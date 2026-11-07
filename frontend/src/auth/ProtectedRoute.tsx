import { CircularProgress, Stack } from '@mui/material'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { useAuth } from './AuthContext'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <Stack sx={{ alignItems: 'center', py: 8 }}>
        <CircularProgress aria-label="Checking your session" />
      </Stack>
    )
  }
  if (status !== 'authenticated') {
    const from = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to="/" replace state={{ from }} />
  }
  return children
}

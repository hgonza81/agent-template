import { Alert, Button, CircularProgress, Stack, Typography } from '@mui/material'

import { useSubscription } from '../api/useSubscription'
import { useAuth } from '../auth/AuthContext'

// The chat UI arrives in Phase 5; for now the page proves the account is
// provisioned before the user enters the chat.
export function ChatPage() {
  const { state, retry } = useSubscription()
  const { signOut } = useAuth()

  if (state.status === 'loading') {
    return (
      <Stack sx={{ alignItems: 'center', py: 8 }}>
        <CircularProgress aria-label="Setting up your account" />
      </Stack>
    )
  }
  if (state.status === 'denied') {
    return (
      <Stack spacing={2}>
        <Alert severity="error" role="alert">
          Your session cannot access this account. Sign out and sign in again.
        </Alert>
        <Button
          variant="outlined"
          sx={{ alignSelf: 'flex-start' }}
          onClick={() => {
            signOut().catch(() => undefined)
          }}
        >
          Sign out
        </Button>
      </Stack>
    )
  }
  if (state.status === 'error') {
    return (
      <Stack spacing={2}>
        <Alert severity="error" role="alert">
          We could not set up your account. Please try again.
        </Alert>
        <Button variant="contained" sx={{ alignSelf: 'flex-start' }} onClick={retry}>
          Try again
        </Button>
      </Stack>
    )
  }
  return (
    <Stack spacing={1}>
      <Typography component="h2" variant="h5">
        Chat
      </Typography>
      {state.subscription.email != null && (
        <Typography color="text.secondary">Signed in as {state.subscription.email}</Typography>
      )}
      <Typography color="text.secondary">The chat experience is coming soon.</Typography>
    </Stack>
  )
}

import { Stack, Typography } from '@mui/material'

// Placeholder behind the protected route; the chat UI arrives in Phase 5.
export function ChatPage() {
  return (
    <Stack spacing={1}>
      <Typography component="h2" variant="h5">
        Chat
      </Typography>
      <Typography color="text.secondary">The chat experience is coming soon.</Typography>
    </Stack>
  )
}

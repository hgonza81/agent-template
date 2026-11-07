import { Alert, Box, Button, Paper, Stack, TextField, Typography } from '@mui/material'
import { useState, type SyntheticEvent } from 'react'

import { sendChatMessage } from '../api/chat'
import { ApiError } from '../api/subscription'
import { useAuth } from '../auth/AuthContext'
import { apiBaseUrl } from '../config'

interface Turn {
  id: number
  role: 'user' | 'agent'
  text: string
}

function describeFailure(error: unknown): string {
  const restored = ' Your text was restored.'
  if (error instanceof ApiError) {
    if (error.status === 429) {
      return `You are sending messages too quickly. Wait a moment and try again.${restored}`
    }
    if (error.status === 422) {
      return `That message is too long or empty. Shorten it and try again.${restored}`
    }
    if (error.status === 504) {
      return `The agent took too long to reply. Please try again.${restored}`
    }
  }
  return `The message could not be sent. Please try again.${restored}`
}

// Plain conversation with the agent. Messages are held only in memory for this
// page view; the server owns the ongoing conversation.
export function ChatPanel() {
  const { getAccessToken } = useAuth()
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)

  const submit = (event: SyntheticEvent) => {
    event.preventDefault()
    const message = draft.trim()
    if (message === '' || sending) {
      return
    }
    setFailure(null)
    setSending(true)
    setTurns((current) => [...current, { id: current.length, role: 'user', text: message }])
    setDraft('')
    getAccessToken()
      .then((token) => sendChatMessage(apiBaseUrl, token, message))
      .then((reply) => {
        setTurns((current) => [...current, { id: current.length, role: 'agent', text: reply }])
      })
      .catch((error: unknown) => {
        setFailure(describeFailure(error))
        setDraft(message)
      })
      .finally(() => {
        setSending(false)
      })
  }

  return (
    <Stack spacing={2}>
      <Box
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        sx={{ display: 'flex', flexDirection: 'column', gap: 1, minHeight: 160 }}
      >
        {turns.length === 0 && (
          <Typography color="text.secondary">Say hello to start the conversation.</Typography>
        )}
        {turns.map((turn) => (
          <Paper
            key={turn.id}
            variant="outlined"
            sx={{ p: 1.5, maxWidth: '85%', alignSelf: turn.role === 'user' ? 'flex-end' : 'flex-start' }}
          >
            <Typography variant="caption" color="text.secondary">
              {turn.role === 'user' ? 'You' : 'Agent'}
            </Typography>
            <Typography sx={{ whiteSpace: 'pre-wrap' }}>{turn.text}</Typography>
          </Paper>
        ))}
        {sending && (
          <Typography color="text.secondary" role="status">
            Agent is replying…
          </Typography>
        )}
      </Box>
      {failure !== null && (
        <Alert severity="error" role="alert">
          {failure}
        </Alert>
      )}
      <Stack component="form" direction="row" spacing={1} onSubmit={submit}>
        <TextField
          fullWidth
          multiline
          maxRows={6}
          label="Message"
          value={draft}
          disabled={sending}
          onChange={(event) => {
            setDraft(event.target.value)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              submit(event)
            }
          }}
        />
        <Button type="submit" variant="contained" disabled={sending || draft.trim() === ''}>
          Send
        </Button>
      </Stack>
    </Stack>
  )
}

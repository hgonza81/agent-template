import { Button, Container, CssBaseline, Stack, Typography } from '@mui/material'
import { Route, Routes } from 'react-router'

import { useAuth } from './auth/AuthContext'
import { CallbackPage } from './auth/CallbackPage'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { ChatPage } from './pages/ChatPage'
import { HomePage } from './pages/HomePage'

function App() {
  const { status, displayName, signOut } = useAuth()

  return (
    <>
      <CssBaseline />
      <Container maxWidth="md">
        <Stack spacing={2} sx={{ py: 8 }}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography component="h1" variant="h4">
              Agent Template
            </Typography>
            {status === 'authenticated' && (
              <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
                {displayName !== null && <Typography>{displayName}</Typography>}
                <Button
                  variant="outlined"
                  onClick={() => {
                    signOut().catch(() => undefined)
                  }}
                >
                  Sign out
                </Button>
              </Stack>
            )}
          </Stack>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/auth/callback" element={<CallbackPage />} />
            <Route
              path="/chat"
              element={
                <ProtectedRoute>
                  <ChatPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<HomePage />} />
          </Routes>
        </Stack>
      </Container>
    </>
  )
}

export default App

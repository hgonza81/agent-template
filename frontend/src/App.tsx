import { Button, Container, CssBaseline, Link, Stack, Typography } from '@mui/material'
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
      <Link
        href="#main"
        sx={{
          position: 'absolute',
          left: -9999,
          '&:focus': { left: 8, top: 8, zIndex: 1, bgcolor: 'background.paper', p: 1 },
        }}
      >
        Skip to main content
      </Link>
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
          <Stack component="main" id="main" tabIndex={-1}>
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
        </Stack>
      </Container>
    </>
  )
}

export default App

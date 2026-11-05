import { Container, CssBaseline, Link, Stack, Typography } from '@mui/material'

import { apiBaseUrl } from './config'

function App() {
  return (
    <>
      <CssBaseline />
      <Container maxWidth="md">
        <Stack spacing={2} sx={{ py: 8 }}>
          <Typography component="h1" variant="h4">
            Agent Template
          </Typography>
          <Typography color="text.secondary">
            Frontend application scaffold.
          </Typography>
          <Link href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer">
            API documentation
          </Link>
        </Stack>
      </Container>
    </>
  )
}

export default App

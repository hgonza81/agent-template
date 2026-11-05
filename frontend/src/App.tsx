import { Container, CssBaseline, Stack, Typography } from '@mui/material'

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
        </Stack>
      </Container>
    </>
  )
}

export default App

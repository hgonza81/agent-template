import { PublicClientApplication } from '@azure/msal-browser'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import './index.css'
import App from './App.tsx'
import { MsalAuthProvider } from './auth/MsalAuthProvider.tsx'
import { createMsalConfiguration } from './auth/msalConfiguration.ts'
import { UnconfiguredAuthProvider } from './auth/UnconfiguredAuthProvider.tsx'
import { authConfig } from './config.ts'

const app = (
  <BrowserRouter>
    <App />
  </BrowserRouter>
)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {authConfig === null ? (
      <UnconfiguredAuthProvider>{app}</UnconfiguredAuthProvider>
    ) : (
      <MsalAuthProvider
        client={new PublicClientApplication(createMsalConfiguration(authConfig, window.location.origin))}
        config={authConfig}
      >
        {app}
      </MsalAuthProvider>
    )}
  </StrictMode>,
)

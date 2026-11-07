import {
  InteractionRequiredAuthError,
  InteractionStatus,
  PromptValue,
  type PublicClientApplication,
} from '@azure/msal-browser'
import { MsalProvider, useMsal } from '@azure/msal-react'
import { useMemo, type ReactNode } from 'react'

import type { AuthConfig } from '../../configuration'
import { AuthContext, type AuthState } from './AuthContext'
import { CALLBACK_PATH } from './msalConfiguration'
import { saveReturnPath } from './returnPath'

interface Props {
  client: PublicClientApplication
  config: AuthConfig
  children: ReactNode
}

function MsalAuthState({ config, children }: Omit<Props, 'client'>) {
  const { instance, accounts, inProgress } = useMsal()
  const account = accounts[0]

  const value = useMemo<AuthState>(() => {
    const redirectUri = `${window.location.origin}${CALLBACK_PATH}`
    const status =
      inProgress !== InteractionStatus.None
        ? 'loading'
        : account !== undefined
          ? 'authenticated'
          : 'unauthenticated'

    return {
      status,
      displayName: account?.name ?? null,
      signIn: async (returnTo) => {
        saveReturnPath(returnTo ?? '/')
        await instance.loginRedirect({ scopes: config.scopes, redirectUri })
      },
      signUp: async (returnTo) => {
        saveReturnPath(returnTo ?? '/')
        await instance.loginRedirect({
          scopes: config.scopes,
          redirectUri,
          prompt: PromptValue.CREATE,
        })
      },
      signOut: async () => {
        await instance.logoutRedirect(account === undefined ? {} : { account })
      },
      getAccessToken: async () => {
        if (account === undefined) {
          throw new Error('Not signed in')
        }
        try {
          const result = await instance.acquireTokenSilent({
            scopes: config.scopes,
            account,
          })
          return result.accessToken
        } catch (error) {
          if (error instanceof InteractionRequiredAuthError) {
            await instance.acquireTokenRedirect({ scopes: config.scopes, account })
          }
          throw error
        }
      },
    }
  }, [account, config.scopes, inProgress, instance])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function MsalAuthProvider({ client, config, children }: Props) {
  return (
    <MsalProvider instance={client}>
      <MsalAuthState config={config}>{children}</MsalAuthState>
    </MsalProvider>
  )
}

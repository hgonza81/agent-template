import type { Configuration } from '@azure/msal-browser'

import type { AuthConfig } from '../../configuration'

export const CALLBACK_PATH = '/auth/callback'

/** Authorization Code + PKCE for a public client: no client secret, ever. */
export function createMsalConfiguration(config: AuthConfig, origin: string): Configuration {
  return {
    auth: {
      clientId: config.clientId,
      authority: config.authority,
      knownAuthorities: [new URL(config.authority).hostname],
      redirectUri: `${origin}${CALLBACK_PATH}`,
      postLogoutRedirectUri: `${origin}/`,
    },
    // MSAL manages tokens; sessionStorage keeps them out of long-lived storage.
    cache: { cacheLocation: 'sessionStorage' },
  }
}

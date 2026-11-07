import type { SubscriptionResponse } from '../generated/Api'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Idempotently provisions (or reads) the caller's free subscription. The
 * server derives identity from the bearer token; nothing else is sent.
 */
export async function fetchSubscription(
  baseUrl: string,
  accessToken: string,
  signal?: AbortSignal,
): Promise<SubscriptionResponse> {
  const init: RequestInit = { headers: { Authorization: `Bearer ${accessToken}` } }
  if (signal !== undefined) {
    init.signal = signal
  }
  const response = await fetch(`${baseUrl}/api/v1/me/subscription`, init)
  if (!response.ok) {
    throw new ApiError(response.status)
  }
  return (await response.json()) as SubscriptionResponse
}

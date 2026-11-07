import { useCallback, useEffect, useState } from 'react'

import { useAuth } from '../auth/AuthContext'
import { apiBaseUrl } from '../config'
import type { SubscriptionResponse } from '../generated/Api'
import { ApiError, fetchSubscription } from './subscription'

export type SubscriptionState =
  | { status: 'loading' }
  | { status: 'ready'; subscription: SubscriptionResponse }
  | { status: 'denied' }
  | { status: 'error' }

export function useSubscription(): { state: SubscriptionState; retry: () => void } {
  const { getAccessToken } = useAuth()
  const [state, setState] = useState<SubscriptionState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    getAccessToken()
      .then((token) => fetchSubscription(apiBaseUrl, token, controller.signal))
      .then((subscription) => {
        setState({ status: 'ready', subscription })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        const denied = error instanceof ApiError && (error.status === 401 || error.status === 403)
        setState({ status: denied ? 'denied' : 'error' })
      })
    return () => {
      controller.abort()
    }
  }, [attempt, getAccessToken])

  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((current) => current + 1)
  }, [])

  return { state, retry }
}

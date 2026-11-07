import type { ChatMessageRequest, ChatMessageResponse } from '../generated/Api'
import { ApiError } from './subscription'

export async function sendChatMessage(
  baseUrl: string,
  accessToken: string,
  message: string,
  signal?: AbortSignal,
): Promise<string> {
  const body: ChatMessageRequest = { message }
  const init: RequestInit = {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  }
  if (signal !== undefined) {
    init.signal = signal
  }
  const response = await fetch(`${baseUrl}/api/v1/chat/messages`, init)
  if (!response.ok) {
    throw new ApiError(response.status)
  }
  return ((await response.json()) as ChatMessageResponse).reply
}

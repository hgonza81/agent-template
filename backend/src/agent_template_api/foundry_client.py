"""Real `FoundryClient` backed by the OpenAI-compatible Foundry endpoint.

Authentication uses `DefaultAzureCredential` (developer `az login` locally,
managed identity in Azure); no keys or secrets are handled. Conversation state
is owned by the provider (Conversations + Responses APIs). The deployment is a
plain model: no instructions, tools, or retrieval are ever sent. Nothing here
logs or records message content.
"""

import asyncio

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncOpenAI, NotFoundError

from agent_template_api.foundry_agent import FoundryThreadNotFoundError

_SCOPE = "https://ai.azure.com/.default"


class OpenAIFoundryClient:
    """`agent_id` is the model deployment name."""

    def __init__(
        self,
        *,
        endpoint: str,
        credential: DefaultAzureCredential | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        sync_provider = get_bearer_token_provider(
            credential or DefaultAzureCredential(), _SCOPE
        )

        async def provider() -> str:
            # Token acquisition is blocking I/O; keep it off the event loop.
            return await asyncio.to_thread(sync_provider)

        self._max_output_tokens = max_output_tokens
        self._client = AsyncOpenAI(
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
            api_key=provider,
            max_retries=0,
        )

    async def create_thread(self) -> str:
        conversation = await self._client.conversations.create()
        return conversation.id

    async def run_message(self, *, thread_id: str, agent_id: str, content: str) -> str:
        try:
            response = await self._client.responses.create(
                model=agent_id,
                conversation=thread_id,
                input=content,
                store=True,
                max_output_tokens=self._max_output_tokens,
            )
        except NotFoundError:
            raise FoundryThreadNotFoundError from None
        return str(response.output_text)

    async def delete_thread(self, thread_id: str) -> None:
        try:
            await self._client.conversations.delete(thread_id)
        except NotFoundError:
            return  # already deleted

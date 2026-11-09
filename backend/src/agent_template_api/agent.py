"""Server-side chat agent interface and a deterministic fake implementation.

The interface is provider-isolated: routes depend on `ChatAgent` only, so the
Azure AI Foundry adapter can replace the fake without touching them. It is a
plain agent: no custom persona/system prompt, tools, or retrieval.
"""

import asyncio
from collections.abc import Callable
from typing import Protocol, runtime_checkable
from uuid import uuid4


class AgentError(Exception):
    """Base class for provider failures; messages must stay content-free.

    `provider_error_type` (exception class name) and `provider_status` (HTTP
    status code) describe the original failure; nothing else from it is kept.
    """

    def __init__(
        self,
        *args: object,
        provider_error_type: str | None = None,
        provider_status: int | None = None,
    ) -> None:
        super().__init__(*args)
        self.provider_error_type = provider_error_type
        self.provider_status = provider_status


class AgentUnavailableError(AgentError):
    """The provider could not be reached or failed to answer."""


class AgentTimeoutError(AgentError):
    """The provider did not answer in time."""


class AgentThreadNotFoundError(AgentError):
    """The provider has no thread with the given reference."""


@runtime_checkable
class ChatAgent(Protocol):
    async def create_thread(self) -> str:
        """Create a provider conversation and return its opaque reference."""
        ...

    async def send_message(self, thread_id: str, message: str) -> str:
        """Append a user message to the thread and return the assistant reply."""
        ...

    async def delete_thread(self, thread_id: str) -> None:
        """Delete the provider conversation; an already-missing one is success."""
        ...


class FakeChatAgent:
    """Deterministic, in-memory agent for local work and tests (no Azure).

    Replies are `Fake reply {n}: {message}`, where n counts the user messages
    in that thread. Failures and delays can be injected to exercise error,
    timeout, and cancellation handling.
    """

    def __init__(
        self,
        *,
        thread_id_factory: Callable[[], str] | None = None,
        delay_seconds: float = 0,
        create_delay_seconds: float = 0,
        error: AgentError | None = None,
    ) -> None:
        self._thread_id_factory = thread_id_factory or (lambda: f"fake-{uuid4()}")
        self.delay_seconds = delay_seconds
        self.create_delay_seconds = create_delay_seconds
        self.error = error
        self._threads: dict[str, list[str]] = {}

    async def create_thread(self) -> str:
        if self.create_delay_seconds:
            await asyncio.sleep(self.create_delay_seconds)
        if self.error is not None:
            raise self.error
        thread_id = self._thread_id_factory()
        self._threads[thread_id] = []
        return thread_id

    async def send_message(self, thread_id: str, message: str) -> str:
        if thread_id not in self._threads:
            raise AgentThreadNotFoundError
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        messages = self._threads[thread_id]
        messages.append(message)
        return f"Fake reply {len(messages)}: {message}"

    async def delete_thread(self, thread_id: str) -> None:
        if self.error is not None:
            raise self.error
        self._threads.pop(thread_id, None)

    def history(self, thread_id: str) -> list[str]:
        """User messages recorded in a thread (test inspection only)."""
        return list(self._threads[thread_id])

    def thread_ids(self) -> list[str]:
        return list(self._threads)


def create_chat_agent(
    provider: str,
    *,
    foundry_project_endpoint: str | None = None,
    foundry_deployment: str | None = None,
) -> ChatAgent:
    """Build the agent for a configured provider name (never falls back)."""
    if provider == "fake":
        return FakeChatAgent()
    if provider == "foundry":
        if not foundry_project_endpoint or not foundry_deployment:
            raise ValueError("Foundry provider is not configured")
        from agent_template_api.foundry_agent import FoundryChatAgent
        from agent_template_api.foundry_client import OpenAIFoundryClient

        return FoundryChatAgent(
            OpenAIFoundryClient(endpoint=foundry_project_endpoint),
            agent_id=foundry_deployment,
        )
    raise ValueError("Unsupported agent provider")


_agent: ChatAgent | None = None


def get_chat_agent() -> ChatAgent:
    """FastAPI dependency: the process-wide agent for the configured provider."""
    global _agent
    if _agent is None:
        from agent_template_api.settings import get_settings

        configured = get_settings()
        endpoint = configured.foundry_project_endpoint
        _agent = create_chat_agent(
            configured.agent_provider,
            foundry_project_endpoint=str(endpoint) if endpoint else None,
            foundry_deployment=configured.foundry_deployment,
        )
    return _agent

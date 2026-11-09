"""Azure AI Foundry adapter for the `ChatAgent` interface.

The adapter talks to Foundry only through the injected `FoundryClient`, so it
carries no SDK or credential handling and is tested with a mock. Provider calls
stay server-side. It never logs, records, or re-raises prompt, message, or
output content: provider failures are mapped to content-free `AgentError`s
with the original exception dropped from the chain.
"""

import asyncio
from typing import Protocol, TypedDict

from agent_template_api.agent import (
    AgentThreadNotFoundError,
    AgentTimeoutError,
    AgentUnavailableError,
)


class _Described(TypedDict):
    provider_error_type: str
    provider_status: int | None


def _describe(error: Exception) -> _Described:
    """Class name and HTTP status only; never the message, body, or headers."""
    status = getattr(error, "status_code", None)
    return {
        "provider_error_type": type(error).__name__,
        "provider_status": status if isinstance(status, int) else None,
    }


class FoundryThreadNotFoundError(Exception):
    """Raised by a `FoundryClient` when the thread does not exist."""


class FoundryClient(Protocol):
    """Minimal provider client; the real SDK wrapper is wired in later."""

    async def create_thread(self) -> str: ...

    async def run_message(self, *, thread_id: str, agent_id: str, content: str) -> str:
        """Add a user message, run the agent, and return the reply text."""
        ...

    async def delete_thread(self, thread_id: str) -> None:
        """Delete the thread; an already-missing thread must count as success."""
        ...


class FoundryChatAgent:
    """Plain agent: no instructions, tools, or retrieval are sent per call."""

    def __init__(self, client: FoundryClient, *, agent_id: str) -> None:
        self._client = client
        self._agent_id = agent_id

    async def create_thread(self) -> str:
        try:
            return await self._client.create_thread()
        except asyncio.CancelledError:
            raise
        except TimeoutError as error:
            raise AgentTimeoutError(**_describe(error)) from None
        except Exception as error:
            raise AgentUnavailableError(**_describe(error)) from None

    async def send_message(self, thread_id: str, message: str) -> str:
        try:
            return await self._client.run_message(
                thread_id=thread_id, agent_id=self._agent_id, content=message
            )
        except asyncio.CancelledError:
            raise
        except FoundryThreadNotFoundError:
            raise AgentThreadNotFoundError(
                provider_error_type="FoundryThreadNotFoundError", provider_status=404
            ) from None
        except TimeoutError as error:
            raise AgentTimeoutError(**_describe(error)) from None
        except Exception as error:
            raise AgentUnavailableError(**_describe(error)) from None

    async def delete_thread(self, thread_id: str) -> None:
        try:
            await self._client.delete_thread(thread_id)
        except asyncio.CancelledError:
            raise
        except TimeoutError as error:
            raise AgentTimeoutError(**_describe(error)) from None
        except Exception as error:
            raise AgentUnavailableError(**_describe(error)) from None

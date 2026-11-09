"""The real Foundry client must send a valid request body.

Regression: `max_output_tokens=None` used to be sent as JSON `null`, which the
provider rejects with 400 (`Expected integer, got Null`). The optional parameter
must be omitted when it is not configured.
"""

import asyncio
import json

import httpx
from azure.core.credentials import AccessToken
from openai import AsyncOpenAI

from agent_template_api.foundry_client import OpenAIFoundryClient


class FakeCredential:
    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        return AccessToken("fake-token", 9_999_999_999)


def _response_json() -> dict[str, object]:
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 1,
        "model": "m",
        "status": "completed",
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "output": [
            {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "ok", "annotations": []}],
            }
        ],
    }


async def _send(max_output_tokens: int | None) -> dict[str, object]:
    sent: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=_response_json())

    client = OpenAIFoundryClient(
        endpoint="https://foundry.example.test/api/projects/p",
        credential=FakeCredential(),  # type: ignore[arg-type]
        max_output_tokens=max_output_tokens,
    )
    inner: AsyncOpenAI = client._client  # noqa: SLF001
    client._client = inner.with_options(  # noqa: SLF001
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    )
    await client.run_message(thread_id="conv_1", agent_id="deployment-1", content="hi")
    return sent[0]


def test_unset_max_output_tokens_is_omitted_not_null() -> None:
    body = asyncio.run(_send(None))
    assert "max_output_tokens" not in body


def test_configured_max_output_tokens_is_sent_as_an_integer() -> None:
    body = asyncio.run(_send(64))
    assert body["max_output_tokens"] == 64

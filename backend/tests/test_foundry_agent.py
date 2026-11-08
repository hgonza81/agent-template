import asyncio
import logging

import pytest

from agent_template_api.agent import (
    AgentThreadNotFoundError,
    AgentTimeoutError,
    AgentUnavailableError,
    ChatAgent,
)
from agent_template_api.foundry_agent import (
    FoundryChatAgent,
    FoundryThreadNotFoundError,
)

SECRET = "secret prompt text"


class MockClient:
    def __init__(self, error: BaseException | None = None, delay: float = 0) -> None:
        self.error = error
        self.delay = delay
        self.calls: list[dict[str, str]] = []
        self.deleted: list[str] = []

    async def delete_thread(self, thread_id: str) -> None:
        if self.error:
            raise self.error
        self.deleted.append(thread_id)

    async def create_thread(self) -> str:
        if self.error:
            raise self.error
        return "thread-1"

    async def run_message(self, *, thread_id: str, agent_id: str, content: str) -> str:
        self.calls.append(
            {"thread_id": thread_id, "agent_id": agent_id, "content": content}
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return "reply"


def test_satisfies_chat_agent_protocol() -> None:
    assert isinstance(FoundryChatAgent(MockClient(), agent_id="a"), ChatAgent)


def test_success_passes_only_message_thread_and_configured_agent() -> None:
    client = MockClient()
    agent = FoundryChatAgent(client, agent_id="agent-1")

    async def scenario() -> tuple[str, str]:
        return await agent.create_thread(), await agent.send_message("thread-1", "hi")

    assert asyncio.run(scenario()) == ("thread-1", "reply")
    assert client.calls == [
        {"thread_id": "thread-1", "agent_id": "agent-1", "content": "hi"}
    ]


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (TimeoutError(SECRET), AgentTimeoutError),
        (FoundryThreadNotFoundError(SECRET), AgentThreadNotFoundError),
        (RuntimeError(SECRET), AgentUnavailableError),
    ],
)
def test_errors_are_mapped_and_content_free(
    raised: Exception, expected: type[Exception]
) -> None:
    agent = FoundryChatAgent(MockClient(error=raised), agent_id="a")
    with pytest.raises(expected) as info:
        asyncio.run(agent.send_message("t", SECRET))
    assert SECRET not in repr(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__


def test_create_thread_errors_are_mapped() -> None:
    unavailable = FoundryChatAgent(MockClient(RuntimeError(SECRET)), agent_id="a")
    with pytest.raises(AgentUnavailableError):
        asyncio.run(unavailable.create_thread())
    timeout = FoundryChatAgent(MockClient(TimeoutError()), agent_id="a")
    with pytest.raises(AgentTimeoutError):
        asyncio.run(timeout.create_thread())


def test_cancellation_propagates() -> None:
    agent = FoundryChatAgent(MockClient(delay=5), agent_id="a")

    async def scenario() -> None:
        task = asyncio.create_task(agent.send_message("t", "hi"))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_adapter_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    ok = FoundryChatAgent(MockClient(), agent_id="a")
    failing = FoundryChatAgent(MockClient(RuntimeError(SECRET)), agent_id="a")

    async def scenario() -> None:
        await ok.send_message("t", SECRET)
        with pytest.raises(AgentUnavailableError):
            await failing.send_message("t", SECRET)

    with caplog.at_level(logging.DEBUG):
        asyncio.run(scenario())
    assert [r for r in caplog.records if r.name != "asyncio"] == []


def test_delete_thread_passes_the_thread_and_maps_errors() -> None:
    client = MockClient()
    asyncio.run(FoundryChatAgent(client, agent_id="a").delete_thread("t-1"))
    assert client.deleted == ["t-1"]

    with pytest.raises(AgentUnavailableError) as unavailable:
        asyncio.run(
            FoundryChatAgent(
                MockClient(error=RuntimeError(SECRET)), agent_id="a"
            ).delete_thread("t-1")
        )
    assert SECRET not in repr(unavailable.value)
    assert unavailable.value.__cause__ is None
    with pytest.raises(AgentTimeoutError):
        asyncio.run(
            FoundryChatAgent(
                MockClient(error=TimeoutError()), agent_id="a"
            ).delete_thread("t-1")
        )

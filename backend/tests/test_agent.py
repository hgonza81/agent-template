import asyncio

import pytest

from agent_template_api.agent import (
    AgentThreadNotFoundError,
    AgentTimeoutError,
    AgentUnavailableError,
    ChatAgent,
    FakeChatAgent,
    create_chat_agent,
)


def test_fake_agent_satisfies_the_interface() -> None:
    assert isinstance(FakeChatAgent(), ChatAgent)
    assert isinstance(create_chat_agent("fake"), FakeChatAgent)
    with pytest.raises(ValueError):
        create_chat_agent("unknown")


def test_replies_are_deterministic_and_counted_per_thread() -> None:
    async def scenario() -> list[str]:
        agent = FakeChatAgent(thread_id_factory=iter(["t1", "t2"]).__next__)
        first = await agent.create_thread()
        second = await agent.create_thread()
        return [
            first,
            second,
            await agent.send_message(first, "hello"),
            await agent.send_message(first, "again"),
            await agent.send_message(second, "hi"),
        ]

    assert asyncio.run(scenario()) == [
        "t1",
        "t2",
        "Fake reply 1: hello",
        "Fake reply 2: again",
        "Fake reply 1: hi",
    ]


def test_default_thread_ids_are_unique_and_opaque() -> None:
    async def scenario() -> tuple[str, str]:
        agent = FakeChatAgent()
        return await agent.create_thread(), await agent.create_thread()

    first, second = asyncio.run(scenario())
    assert first != second
    assert first.startswith("fake-")


def test_unknown_threads_are_rejected() -> None:
    with pytest.raises(AgentThreadNotFoundError):
        asyncio.run(FakeChatAgent().send_message("missing", "hello"))


def test_injected_failures_surface_without_message_content() -> None:
    async def scenario(error: Exception) -> None:
        agent = FakeChatAgent()
        thread = await agent.create_thread()
        agent.error = (
            AgentUnavailableError()
            if isinstance(error, AgentUnavailableError)
            else AgentTimeoutError()
        )
        await agent.send_message(thread, "secret prompt")

    for error in (AgentUnavailableError(), AgentTimeoutError()):
        with pytest.raises(type(error)) as raised:
            asyncio.run(scenario(error))
        assert "secret prompt" not in str(raised.value)


def test_injected_delay_can_be_cancelled() -> None:
    async def scenario() -> None:
        agent = FakeChatAgent(delay_seconds=30)
        thread = await agent.create_thread()
        await asyncio.wait_for(agent.send_message(thread, "slow"), timeout=0.05)

    with pytest.raises(TimeoutError):
        asyncio.run(scenario())


def test_unknown_provider_is_rejected_by_settings() -> None:
    from pydantic import ValidationError

    from agent_template_api.settings import Settings

    with pytest.raises(ValidationError):
        Settings(
            cors_allowed_origins=["http://127.0.0.1:5173"],
            database_url="postgresql+psycopg://u:p@localhost/app",
            agent_provider="openai",
            _env_file=None,
        )


def test_foundry_provider_requires_configuration_and_never_falls_back() -> None:
    with pytest.raises(ValueError):
        create_chat_agent("foundry")
    with pytest.raises(ValueError):
        create_chat_agent("foundry", foundry_project_endpoint="https://x.example/")


def test_foundry_provider_builds_the_adapter_without_network() -> None:
    from agent_template_api.foundry_agent import FoundryChatAgent

    agent = create_chat_agent(
        "foundry",
        foundry_project_endpoint="https://x.example/",
        foundry_deployment="chat",
    )
    assert isinstance(agent, FoundryChatAgent)

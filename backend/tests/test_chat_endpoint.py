from collections.abc import Iterator
from types import ModuleType
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from agent_template_api.agent import (
    AgentUnavailableError,
    FakeChatAgent,
    get_chat_agent,
)
from agent_template_api.auth import TokenIdentity, get_current_identity
from agent_template_api.models import Subscription

ISSUER = "https://issuer.example.test/tenant/v2.0"


@pytest.fixture
def api_module(monkeypatch: MonkeyPatch) -> Iterator[ModuleType]:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]')
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://agent_template:local-dev-only"
        "@127.0.0.1:5433/agent_template_test",
    )
    from agent_template_api import main

    assert main.database_engine.url.database == "agent_template_test"
    command.upgrade(Config("alembic.ini"), "head")
    yield main
    main.app.dependency_overrides.clear()


@pytest.fixture
def agent(api_module: ModuleType) -> FakeChatAgent:
    fake = FakeChatAgent()
    api_module.app.dependency_overrides[get_chat_agent] = lambda: fake
    return fake


@pytest.fixture
def subject(api_module: ModuleType) -> Iterator[str]:
    value = f"chat-{uuid4()}"
    api_module.app.dependency_overrides[get_current_identity] = lambda: TokenIdentity(
        issuer=ISSUER, subject=value, scopes=frozenset({"chat.use"})
    )
    yield value
    with Session(api_module.database_engine) as session, session.begin():
        session.execute(
            delete(Subscription).where(Subscription.identity_subject == value)
        )


def stored_thread(api_module: ModuleType, subject: str) -> str | None:
    with Session(api_module.database_engine) as session:
        return session.execute(
            select(Subscription.foundry_thread_id).where(
                Subscription.identity_subject == subject
            )
        ).scalar_one_or_none()


def test_chat_requires_authentication(api_module: ModuleType) -> None:
    with TestClient(api_module.app) as client:
        response = client.post("/api/v1/chat/messages", json={"message": "hi"})

    assert response.status_code == 401


def test_message_returns_the_agent_reply(
    api_module: ModuleType, agent: FakeChatAgent, subject: str
) -> None:
    with TestClient(api_module.app) as client:
        response = client.post("/api/v1/chat/messages", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Fake reply 1: hello"}


def test_conversation_persists_across_messages(
    api_module: ModuleType, agent: FakeChatAgent, subject: str
) -> None:
    with TestClient(api_module.app) as client:
        first = client.post("/api/v1/chat/messages", json={"message": "one"})
        second = client.post("/api/v1/chat/messages", json={"message": "two"})

    assert first.json()["reply"] == "Fake reply 1: one"
    assert second.json()["reply"] == "Fake reply 2: two"
    assert len(agent.thread_ids()) == 1
    assert stored_thread(api_module, subject) == agent.thread_ids()[0]


def test_provider_failure_returns_generic_503(
    api_module: ModuleType, agent: FakeChatAgent, subject: str
) -> None:
    agent.error = AgentUnavailableError("provider secret detail")
    with TestClient(api_module.app) as client:
        response = client.post("/api/v1/chat/messages", json={"message": "hi"})

    assert response.status_code == 503
    assert "secret" not in response.text
    assert stored_thread(api_module, subject) is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": ""},
        {"message": "hi", "user_id": "x"},
        {"message": "hi", "thread_id": "x"},
        {"message": "hi", "subscription_id": "x"},
        {"message": "hi", "agent_id": "x"},
    ],
)
def test_invalid_bodies_are_rejected(
    api_module: ModuleType, agent: FakeChatAgent, subject: str, body: dict[str, str]
) -> None:
    with TestClient(api_module.app) as client:
        response = client.post("/api/v1/chat/messages", json=body)

    assert response.status_code == 422
    assert agent.thread_ids() == []


def test_concurrent_first_messages_create_exactly_one_thread(
    api_module: ModuleType, subject: str
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    slow = FakeChatAgent(create_delay_seconds=0.3)
    api_module.app.dependency_overrides[get_chat_agent] = lambda: slow

    def send(index: int) -> int:
        with TestClient(api_module.app) as client:
            return client.post(
                "/api/v1/chat/messages", json={"message": f"m{index}"}
            ).status_code

    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses = list(pool.map(send, range(5)))

    assert statuses == [200] * 5
    assert len(slow.thread_ids()) == 1
    assert stored_thread(api_module, subject) == slow.thread_ids()[0]


def test_failed_thread_creation_stores_nothing_and_is_retried(
    api_module: ModuleType, agent: FakeChatAgent, subject: str
) -> None:
    agent.error = AgentUnavailableError()
    with TestClient(api_module.app) as client:
        failed = client.post("/api/v1/chat/messages", json={"message": "hi"})
        assert failed.status_code == 503
        assert stored_thread(api_module, subject) is None

        agent.error = None
        retried = client.post("/api/v1/chat/messages", json={"message": "hi"})

    assert retried.status_code == 200
    assert len(agent.thread_ids()) == 1


def test_each_subscription_gets_its_own_thread(
    api_module: ModuleType, agent: FakeChatAgent, subject: str
) -> None:
    other = f"{subject}-other"
    try:
        with TestClient(api_module.app) as client:
            client.post("/api/v1/chat/messages", json={"message": "mine"})
            api_module.app.dependency_overrides[get_current_identity] = lambda: (
                TokenIdentity(issuer=ISSUER, subject=other, scopes=frozenset())
            )
            theirs = client.post("/api/v1/chat/messages", json={"message": "theirs"})

        assert theirs.json()["reply"] == "Fake reply 1: theirs"
        assert len(agent.thread_ids()) == 2
        assert stored_thread(api_module, subject) != stored_thread(api_module, other)
    finally:
        with Session(api_module.database_engine) as session, session.begin():
            session.execute(
                delete(Subscription).where(Subscription.identity_subject == other)
            )

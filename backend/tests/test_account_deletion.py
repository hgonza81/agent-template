from collections.abc import Iterator
from types import ModuleType
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import delete, func, select
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
    with Session(main.database_engine) as session, session.begin():
        session.execute(
            delete(Subscription).where(Subscription.identity_subject.like("deletion-%"))
        )


@pytest.fixture
def agent(api_module: ModuleType) -> FakeChatAgent:
    fake = FakeChatAgent()
    api_module.app.dependency_overrides[get_chat_agent] = lambda: fake
    return fake


def authenticate_as(api_module: ModuleType, subject: str) -> None:
    api_module.app.dependency_overrides[get_current_identity] = lambda: TokenIdentity(
        issuer=ISSUER, subject=subject, scopes=frozenset({"chat.use"})
    )


def count(api_module: ModuleType, subject: str) -> int:
    with Session(api_module.database_engine) as session:
        return session.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.identity_subject == subject)
        ).scalar_one()


def chat_as(api_module: ModuleType, client: TestClient, subject: str) -> None:
    authenticate_as(api_module, subject)
    assert (
        client.post("/api/v1/chat/messages", json={"message": "hi"}).status_code == 200
    )


def test_deletes_the_conversation_then_the_subscription(
    api_module: ModuleType, agent: FakeChatAgent
) -> None:
    subject = f"deletion-{uuid4()}"
    with TestClient(api_module.app) as client:
        chat_as(api_module, client, subject)
        assert len(agent.thread_ids()) == 1
        response = client.delete("/api/v1/me")

    assert response.status_code == 204
    assert response.content == b""
    assert agent.thread_ids() == []
    assert count(api_module, subject) == 0


def test_account_without_a_conversation_is_deleted(
    api_module: ModuleType, agent: FakeChatAgent
) -> None:
    subject = f"deletion-{uuid4()}"
    authenticate_as(api_module, subject)
    with TestClient(api_module.app) as client:
        assert client.get("/api/v1/me/subscription").status_code == 200
        assert client.delete("/api/v1/me").status_code == 204
    assert count(api_module, subject) == 0


def test_deleting_twice_is_a_no_op(
    api_module: ModuleType, agent: FakeChatAgent
) -> None:
    authenticate_as(api_module, f"deletion-{uuid4()}")
    with TestClient(api_module.app) as client:
        assert client.delete("/api/v1/me").status_code == 204
        assert client.delete("/api/v1/me").status_code == 204


def test_provider_failure_keeps_the_subscription_and_is_generic_then_retry_works(
    api_module: ModuleType, agent: FakeChatAgent
) -> None:
    subject = f"deletion-{uuid4()}"
    with TestClient(api_module.app) as client:
        chat_as(api_module, client, subject)
        agent.error = AgentUnavailableError("secret-provider-detail")
        failed = client.delete("/api/v1/me")

        assert failed.status_code == 503
        assert set(failed.json()) == {"detail", "request_id"}
        assert "secret-provider-detail" not in failed.text
        assert count(api_module, subject) == 1
        assert len(agent.thread_ids()) == 1

        agent.error = None
        retried = client.delete("/api/v1/me")

    assert retried.status_code == 204
    assert agent.thread_ids() == []
    assert count(api_module, subject) == 0


def test_conversation_already_gone_at_the_provider_counts_as_deleted(
    api_module: ModuleType, agent: FakeChatAgent
) -> None:
    subject = f"deletion-{uuid4()}"
    with TestClient(api_module.app) as client:
        chat_as(api_module, client, subject)
        # Simulates a partial failure: provider thread removed, row still there.
        for thread_id in agent.thread_ids():
            import asyncio

            asyncio.run(agent.delete_thread(thread_id))
        response = client.delete("/api/v1/me")

    assert response.status_code == 204
    assert count(api_module, subject) == 0


def test_a_user_cannot_delete_another_users_data(
    api_module: ModuleType, agent: FakeChatAgent
) -> None:
    alice = f"deletion-{uuid4()}"
    bob = f"deletion-{uuid4()}"
    with TestClient(api_module.app) as client:
        chat_as(api_module, client, alice)
        chat_as(api_module, client, bob)
        assert len(agent.thread_ids()) == 2

        authenticate_as(api_module, bob)
        # The client cannot name a target: query/body input is ignored.
        response = client.delete(f"/api/v1/me?subject={alice}")

    assert response.status_code == 204
    assert count(api_module, bob) == 0
    assert count(api_module, alice) == 1
    assert len(agent.thread_ids()) == 1


def test_requires_a_valid_token(api_module: ModuleType, agent: FakeChatAgent) -> None:
    subject = f"deletion-{uuid4()}"
    with TestClient(api_module.app) as client:
        chat_as(api_module, client, subject)
        api_module.app.dependency_overrides.pop(get_current_identity)
        missing = client.delete("/api/v1/me")
        invalid = client.delete("/api/v1/me", headers={"Authorization": "Bearer junk"})

    assert missing.status_code == 401
    # Auth is not configured in tests, so a token cannot be validated.
    assert invalid.status_code == 503
    assert count(api_module, subject) == 1
    assert len(agent.thread_ids()) == 1

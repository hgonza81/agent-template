"""End-to-end local chat flow: real token validation, database, and fake agent.

Tokens come from the loopback OIDC issuer used by the identity flow tests, so
the whole request path (bearer validation -> subscription -> thread -> agent)
runs without Azure or a real tenant.
"""

from collections.abc import Iterator
from types import ModuleType
from uuid import uuid4

import pytest
import test_local_identity_flow as flow
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from test_local_identity_flow import AUDIENCE, SCOPE, LocalIssuer

from agent_template_api.agent import FakeChatAgent, get_chat_agent
from agent_template_api.auth import TokenValidator, fetch_json, token_validator_provider
from agent_template_api.models import Subscription

# Reuse the loopback issuer and test-database fixtures.
api_module = flow.api_module
issuer = flow.issuer


@pytest.fixture
def agent(api_module: ModuleType) -> FakeChatAgent:
    fake = FakeChatAgent()
    api_module.app.dependency_overrides[get_chat_agent] = lambda: fake
    return fake


@pytest.fixture
def client(
    api_module: ModuleType, issuer: LocalIssuer, agent: FakeChatAgent
) -> Iterator[TestClient]:
    validator = TokenValidator(
        issuer=issuer.url,
        discovery_url=issuer.discovery_url,
        audience=AUDIENCE,
        required_scope=SCOPE,
        fetcher=fetch_json,
    )
    api_module.app.dependency_overrides[token_validator_provider] = lambda: (
        lambda: validator
    )
    with TestClient(api_module.app) as test_client:
        yield test_client


@pytest.fixture
def users(api_module: ModuleType) -> Iterator[tuple[str, str]]:
    alice, bob = f"alice-{uuid4()}", f"bob-{uuid4()}"
    yield alice, bob
    with Session(api_module.database_engine) as session, session.begin():
        session.execute(
            delete(Subscription).where(Subscription.identity_subject.in_([alice, bob]))
        )


def say(
    client: TestClient, issuer: LocalIssuer, subject: str, message: str, **extra: str
) -> tuple[int, dict[str, str]]:
    response = client.post(
        "/api/v1/chat/messages",
        json={"message": message, **extra},
        headers={"Authorization": f"Bearer {issuer.mint(subject)}"},
    )
    body: dict[str, str] = response.json()
    return response.status_code, body


def thread_of(api_module: ModuleType, subject: str) -> str:
    with Session(api_module.database_engine) as session:
        thread = session.execute(
            select(Subscription.foundry_thread_id).where(
                Subscription.identity_subject == subject
            )
        ).scalar_one()
    assert thread is not None
    return thread


def test_signed_in_user_has_one_persistent_conversation(
    api_module: ModuleType,
    client: TestClient,
    issuer: LocalIssuer,
    agent: FakeChatAgent,
    users: tuple[str, str],
) -> None:
    alice, _ = users

    first = say(client, issuer, alice, "hello")
    second = say(client, issuer, alice, "again")

    assert first == (200, {"reply": "Fake reply 1: hello"})
    assert second == (200, {"reply": "Fake reply 2: again"})
    assert agent.thread_ids() == [thread_of(api_module, alice)]
    assert agent.history(thread_of(api_module, alice)) == ["hello", "again"]


def test_a_user_cannot_read_or_write_another_users_conversation(
    api_module: ModuleType,
    client: TestClient,
    issuer: LocalIssuer,
    agent: FakeChatAgent,
    users: tuple[str, str],
) -> None:
    alice, bob = users
    say(client, issuer, alice, "alice secret one")
    say(client, issuer, alice, "alice secret two")
    alice_thread = thread_of(api_module, alice)

    status, body = say(client, issuer, bob, "bob hello")

    # Bob starts his own conversation: his reply counter starts at 1 and
    # nothing Alice said appears in his reply.
    assert status == 200
    assert body == {"reply": "Fake reply 1: bob hello"}
    assert "secret" not in str(body)
    bob_thread = thread_of(api_module, bob)
    assert bob_thread != alice_thread
    assert agent.history(alice_thread) == ["alice secret one", "alice secret two"]
    assert agent.history(bob_thread) == ["bob hello"]


@pytest.mark.parametrize(
    "field",
    ["thread_id", "foundry_thread_id", "subscription_id", "user_id", "agent_id"],
)
def test_client_cannot_target_another_conversation_by_id(
    api_module: ModuleType,
    client: TestClient,
    issuer: LocalIssuer,
    agent: FakeChatAgent,
    users: tuple[str, str],
    field: str,
) -> None:
    alice, bob = users
    say(client, issuer, alice, "private")
    alice_thread = thread_of(api_module, alice)

    status, _ = say(client, issuer, bob, "intrude", **{field: alice_thread})

    assert status == 422
    assert agent.history(alice_thread) == ["private"]
    assert len(agent.thread_ids()) == 1  # Bob never even got a thread


def test_each_token_only_ever_sees_its_own_subscription(
    client: TestClient, issuer: LocalIssuer, users: tuple[str, str]
) -> None:
    alice, bob = users

    def subscription(subject: str) -> dict[str, str]:
        body: dict[str, str] = client.get(
            "/api/v1/me/subscription",
            headers={"Authorization": f"Bearer {issuer.mint(subject)}"},
            params={"subject": alice},
        ).json()
        return body

    assert subscription(alice)["id"] != subscription(bob)["id"]


def test_chat_requires_a_valid_token_and_scope(
    api_module: ModuleType,
    client: TestClient,
    issuer: LocalIssuer,
    agent: FakeChatAgent,
    users: tuple[str, str],
) -> None:
    alice, _ = users
    body = {"message": "hi"}

    assert client.post("/api/v1/chat/messages", json=body).status_code == 401
    no_scope = client.post(
        "/api/v1/chat/messages",
        json=body,
        headers={"Authorization": f"Bearer {issuer.mint(alice, scp='other')}"},
    )

    assert no_scope.status_code == 403
    assert agent.thread_ids() == []


def test_interleaved_users_keep_separate_histories(
    api_module: ModuleType,
    client: TestClient,
    issuer: LocalIssuer,
    agent: FakeChatAgent,
    users: tuple[str, str],
) -> None:
    alice, bob = users

    for turn in range(3):
        say(client, issuer, alice, f"a{turn}")
        say(client, issuer, bob, f"b{turn}")

    assert agent.history(thread_of(api_module, alice)) == ["a0", "a1", "a2"]
    assert agent.history(thread_of(api_module, bob)) == ["b0", "b1", "b2"]

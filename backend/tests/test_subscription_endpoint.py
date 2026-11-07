from collections.abc import Iterator
from types import ModuleType
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import Table, delete, func, select
from sqlalchemy.orm import Session

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
def subject(api_module: ModuleType) -> Iterator[str]:
    value = f"test-{uuid4()}"
    yield value
    with Session(api_module.database_engine) as session, session.begin():
        session.execute(
            delete(Subscription).where(Subscription.identity_subject == value)
        )


def authenticate_as(
    api_module: ModuleType, subject: str, email: str | None = "Ada@Example.test"
) -> None:
    api_module.app.dependency_overrides[get_current_identity] = lambda: TokenIdentity(
        issuer=ISSUER, subject=subject, scopes=frozenset({"chat.use"}), email=email
    )


def count(api_module: ModuleType, subject: str) -> int:
    with Session(api_module.database_engine) as session:
        return session.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.identity_subject == subject)
        ).scalar_one()


def test_first_request_provisions_subscription(
    api_module: ModuleType, subject: str
) -> None:
    authenticate_as(api_module, subject)
    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/me/subscription")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "started_at", "email"}
    assert body["email"] == "ada@example.test"
    assert body["started_at"].endswith(("Z", "+00:00"))
    assert count(api_module, subject) == 1


def test_repeated_requests_return_the_same_subscription(
    api_module: ModuleType, subject: str
) -> None:
    authenticate_as(api_module, subject)
    with TestClient(api_module.app) as client:
        first = client.get("/api/v1/me/subscription").json()
        second = client.get("/api/v1/me/subscription").json()

    assert first == second
    assert count(api_module, subject) == 1


def test_endpoint_requires_a_valid_bearer_token(api_module: ModuleType) -> None:
    with TestClient(api_module.app) as client:
        missing = client.get("/api/v1/me/subscription")
        invalid = client.get(
            "/api/v1/me/subscription", headers={"Authorization": "Bearer junk"}
        )

    assert missing.status_code == 401
    # Auth is not configured in tests, so a token cannot be validated yet.
    assert invalid.status_code == 503
    assert "request_id" in missing.json()


def test_request_input_cannot_choose_identity_or_email(
    api_module: ModuleType, subject: str
) -> None:
    authenticate_as(api_module, subject, email="real@example.test")
    with TestClient(api_module.app) as client:
        response = client.get(
            "/api/v1/me/subscription",
            params={"subject": "someone-else", "email": "forged@example.test"},
            headers={"X-Subject": "someone-else", "X-Email": "forged@example.test"},
        )

    assert response.json()["email"] == "real@example.test"
    assert count(api_module, "someone-else") == 0


def test_database_failure_returns_generic_503(
    monkeypatch: MonkeyPatch, api_module: ModuleType, subject: str
) -> None:
    from sqlalchemy.exc import OperationalError

    def fail(*_: object) -> None:
        raise OperationalError("INSERT", {}, RuntimeError("secret-host"))

    monkeypatch.setattr(api_module, "provision_subscription", fail)
    authenticate_as(api_module, subject)
    with TestClient(api_module.app) as client:
        response = client.get("/api/v1/me/subscription")

    assert response.status_code == 503
    assert "secret-host" not in response.text


def email_of(api_module: ModuleType, subject: str) -> str | None:
    with Session(api_module.database_engine) as session:
        return session.execute(
            select(Subscription.email_snapshot).where(
                Subscription.identity_subject == subject
            )
        ).scalar_one()


def test_changed_email_updates_the_snapshot_without_a_new_subscription(
    api_module: ModuleType, subject: str
) -> None:
    with TestClient(api_module.app) as client:
        authenticate_as(api_module, subject, email="old@example.test")
        first = client.get("/api/v1/me/subscription").json()
        authenticate_as(api_module, subject, email="New@Example.test")
        second = client.get("/api/v1/me/subscription").json()

    assert second["id"] == first["id"]
    assert second["email"] == "new@example.test"
    assert count(api_module, subject) == 1


@pytest.mark.parametrize("claim", [None, "", "   ", "not-an-email"])
def test_missing_or_invalid_email_never_clears_the_snapshot(
    api_module: ModuleType, subject: str, claim: str | None
) -> None:
    with TestClient(api_module.app) as client:
        authenticate_as(api_module, subject, email="keep@example.test")
        client.get("/api/v1/me/subscription")
        authenticate_as(api_module, subject, email=claim)
        response = client.get("/api/v1/me/subscription")

    assert response.json()["email"] == "keep@example.test"
    assert email_of(api_module, subject) == "keep@example.test"


def test_shared_email_does_not_merge_identities(
    api_module: ModuleType, subject: str
) -> None:
    other = f"{subject}-other"
    try:
        with TestClient(api_module.app) as client:
            authenticate_as(api_module, subject, email="shared@example.test")
            first = client.get("/api/v1/me/subscription").json()
            authenticate_as(api_module, other, email="shared@example.test")
            second = client.get("/api/v1/me/subscription").json()

        assert first["id"] != second["id"]
        assert count(api_module, subject) == 1
        assert count(api_module, other) == 1
    finally:
        with Session(api_module.database_engine) as session, session.begin():
            session.execute(
                delete(Subscription).where(Subscription.identity_subject == other)
            )


def test_same_subject_from_another_issuer_is_a_separate_subscription(
    api_module: ModuleType, subject: str
) -> None:
    from agent_template_api.subscriptions import provision_subscription

    first = provision_subscription(
        api_module.database_engine,
        TokenIdentity(issuer=ISSUER, subject=subject, scopes=frozenset()),
    )
    second = provision_subscription(
        api_module.database_engine,
        TokenIdentity(issuer=ISSUER + "-b", subject=subject, scopes=frozenset()),
    )

    assert first.id != second.id


def test_email_is_not_indexed_or_unique_so_it_cannot_identify_accounts() -> None:
    table = Subscription.__table__
    assert isinstance(table, Table)
    email_column = table.c.email_snapshot
    assert not email_column.unique
    assert not email_column.index
    assert all(email_column not in index.columns for index in table.indexes)
    assert all(
        email_column.name not in {c.name for c in constraint.columns}
        for constraint in table.constraints
        if hasattr(constraint, "columns")
    )

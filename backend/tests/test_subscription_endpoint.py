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


def test_concurrent_first_requests_create_exactly_one_subscription(
    api_module: ModuleType, subject: str
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from agent_template_api.subscriptions import provision_subscription

    workers = 8
    barrier = Barrier(workers)
    identity = TokenIdentity(
        issuer=ISSUER, subject=subject, scopes=frozenset(), email="c@example.test"
    )

    def provision() -> str:
        barrier.wait(timeout=10)
        return str(provision_subscription(api_module.database_engine, identity).id)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        ids = list(pool.map(lambda _: provision(), range(workers)))

    assert len(set(ids)) == 1
    assert count(api_module, subject) == 1


def test_retry_after_a_failed_attempt_provisions_once(
    monkeypatch: MonkeyPatch, api_module: ModuleType, subject: str
) -> None:
    from sqlalchemy.exc import OperationalError

    import agent_template_api.subscriptions as subscriptions

    authenticate_as(api_module, subject)
    real_normalize = subscriptions.normalize_email
    calls = {"n": 0}

    def flaky(email: str | None) -> str | None:
        calls["n"] += 1
        if calls["n"] == 2:  # after the insert, before commit
            raise OperationalError("SELECT", {}, RuntimeError("connection lost"))
        return real_normalize(email)

    monkeypatch.setattr(subscriptions, "normalize_email", flaky)
    with TestClient(api_module.app) as client:
        failed = client.get("/api/v1/me/subscription")
        assert failed.status_code == 503
        assert count(api_module, subject) == 0  # the failed transaction rolled back
        retried = client.get("/api/v1/me/subscription")
        again = client.get("/api/v1/me/subscription")

    assert retried.status_code == 200
    assert retried.json() == again.json()
    assert count(api_module, subject) == 1


class TestAuthorizationBoundaries:
    """Real token validation in front of the endpoint; no rows on rejection."""

    @pytest.fixture
    def validated_client(
        self, api_module: ModuleType
    ) -> Iterator[tuple[TestClient, str]]:
        from test_auth import (
            AUDIENCE,
            DISCOVERY,
            SCOPE,
            Fetcher,
        )
        from test_auth import (
            ISSUER as TOKEN_ISSUER,
        )

        from agent_template_api.auth import TokenValidator, token_validator_provider

        validator = TokenValidator(
            issuer=TOKEN_ISSUER,
            discovery_url=DISCOVERY,
            audience=AUDIENCE,
            required_scope=SCOPE,
            fetcher=Fetcher(),
        )
        api_module.app.dependency_overrides[token_validator_provider] = lambda: (
            lambda: validator
        )
        with TestClient(api_module.app) as client:
            yield client, TOKEN_ISSUER

    def get(self, client: TestClient, token: str | None) -> int:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return client.get("/api/v1/me/subscription", headers=headers).status_code

    def test_valid_token_provisions_by_issuer_and_subject(
        self,
        api_module: ModuleType,
        subject: str,
        validated_client: tuple[TestClient, str],
    ) -> None:
        from test_auth import token

        client, _ = validated_client
        assert self.get(client, token(sub=subject)) == 200
        assert self.get(client, token(sub=subject)) == 200
        assert count(api_module, subject) == 1

    def test_rejected_tokens_never_create_a_subscription(
        self,
        api_module: ModuleType,
        subject: str,
        validated_client: tuple[TestClient, str],
    ) -> None:
        import time

        from test_auth import OTHER_KEY, token

        client, _ = validated_client
        expected = {
            "missing": (None, 401),
            "garbage": ("junk", 401),
            "wrong-issuer": (token(sub=subject, iss="https://evil.example.test"), 401),
            "wrong-audience": (token(sub=subject, aud="api://other"), 401),
            "expired": (token(sub=subject, exp=int(time.time()) - 3600), 401),
            "bad-signature": (token(sub=subject, key=OTHER_KEY), 401),
            "insufficient-scope": (token(sub=subject, scp="other"), 403),
        }
        for name, (value, status) in expected.items():
            assert self.get(client, value) == status, name
        assert count(api_module, subject) == 0

    def test_a_token_only_reaches_its_own_subscription(
        self,
        api_module: ModuleType,
        subject: str,
        validated_client: tuple[TestClient, str],
    ) -> None:
        from test_auth import token

        client, _ = validated_client
        other = f"{subject}-other"
        try:
            mine = client.get(
                "/api/v1/me/subscription",
                headers={"Authorization": f"Bearer {token(sub=subject)}"},
                params={"subscription_id": "anything"},
            ).json()
            theirs = client.get(
                "/api/v1/me/subscription",
                headers={"Authorization": f"Bearer {token(sub=other)}"},
            ).json()
            assert mine["id"] != theirs["id"]
        finally:
            with Session(api_module.database_engine) as session, session.begin():
                session.execute(
                    delete(Subscription).where(Subscription.identity_subject == other)
                )

"""API flow tests against a local OIDC issuer served over real HTTP.

Safe test identity strategy: tokens are minted with a throwaway RSA key and
validated by the production TokenValidator and default HTTP fetcher against a
loopback discovery/JWKS server. No real tenant, credential, or external
network is involved.
"""

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import ModuleType
from typing import Any
from uuid import uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from pytest import MonkeyPatch
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from agent_template_api.auth import (
    IdentityProviderUnavailableError,
    TokenValidator,
    fetch_json,
    token_validator_provider,
)
from agent_template_api.models import Subscription

AUDIENCE = "api://local-test"
SCOPE = "chat.use"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class LocalIssuer:
    def __init__(self) -> None:
        self.requests: list[str] = []
        issuer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                issuer.requests.append(self.path)
                if self.path == "/.well-known/openid-configuration":
                    body: Any = {
                        "issuer": issuer.url,
                        "jwks_uri": f"{issuer.url}/keys",
                    }
                elif self.path == "/keys":
                    jwk = RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
                    body = {"keys": [{**jwk, "kid": "local-1", "use": "sig"}]}
                else:
                    self.send_error(404)
                    return
                payload = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def discovery_url(self) -> str:
        return f"{self.url}/.well-known/openid-configuration"

    def mint(self, subject: str, **overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": self.url,
            "aud": AUDIENCE,
            "sub": subject,
            "exp": now + 600,
            "nbf": now - 5,
            "scp": SCOPE,
            "email": "local.user@example.test",
        }
        claims.update(overrides)
        return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "local-1"})


@pytest.fixture(scope="module")
def issuer() -> Iterator[LocalIssuer]:
    local = LocalIssuer()
    local.thread.start()
    yield local
    local.server.shutdown()
    local.server.server_close()


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
def client(api_module: ModuleType, issuer: LocalIssuer) -> Iterator[TestClient]:
    validator = TokenValidator(
        issuer=issuer.url,
        discovery_url=issuer.discovery_url,
        audience=AUDIENCE,
        required_scope=SCOPE,
        # The production fetcher over real HTTP to the loopback issuer.
        fetcher=fetch_json,
    )
    api_module.app.dependency_overrides[token_validator_provider] = lambda: (
        lambda: validator
    )
    with TestClient(api_module.app) as test_client:
        yield test_client


@pytest.fixture
def subject(api_module: ModuleType) -> Iterator[str]:
    value = f"local-{uuid4()}"
    yield value
    with Session(api_module.database_engine) as session, session.begin():
        session.execute(
            delete(Subscription).where(Subscription.identity_subject == value)
        )


def rows(api_module: ModuleType, subject: str) -> int:
    with Session(api_module.database_engine) as session:
        return session.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.identity_subject == subject)
        ).scalar_one()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_sign_up_then_repeat_visits_use_one_subscription(
    api_module: ModuleType, client: TestClient, issuer: LocalIssuer, subject: str
) -> None:
    token = issuer.mint(subject)
    first = client.get("/api/v1/me/subscription", headers=bearer(token))
    again = client.get("/api/v1/me/subscription", headers=bearer(issuer.mint(subject)))

    assert first.status_code == 200
    assert first.json() == again.json()
    assert first.json()["email"] == "local.user@example.test"
    assert rows(api_module, subject) == 1


def test_identity_is_the_issuer_subject_pair(
    api_module: ModuleType, client: TestClient, issuer: LocalIssuer, subject: str
) -> None:
    with Session(api_module.database_engine) as session:
        client.get("/api/v1/me/subscription", headers=bearer(issuer.mint(subject)))
        stored = session.execute(
            select(Subscription).where(Subscription.identity_subject == subject)
        ).scalar_one()

    assert stored.identity_issuer == issuer.url


def test_rejected_tokens_do_not_provision_and_do_not_leak_details(
    api_module: ModuleType, client: TestClient, issuer: LocalIssuer, subject: str
) -> None:
    rejected = [
        issuer.mint(subject, aud="api://someone-else"),
        issuer.mint(subject, iss="https://other.example.test"),
        issuer.mint(subject, exp=int(time.time()) - 600),
        issuer.mint(subject, scp="unrelated"),
    ]
    for token in rejected:
        response = client.get("/api/v1/me/subscription", headers=bearer(token))
        assert response.status_code in {401, 403}
        assert set(response.json()) == {"detail", "request_id"}
        assert token not in response.text

    assert rows(api_module, subject) == 0


def test_signing_keys_are_fetched_once_and_cached(
    client: TestClient, issuer: LocalIssuer, subject: str
) -> None:
    issuer.requests.clear()
    for _ in range(3):
        client.get("/api/v1/me/subscription", headers=bearer(issuer.mint(subject)))

    assert issuer.requests.count("/keys") <= 1


def test_default_fetcher_reports_unreachable_providers() -> None:
    with pytest.raises(IdentityProviderUnavailableError):
        fetch_json("http://127.0.0.1:1/.well-known/openid-configuration")

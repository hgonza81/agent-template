"""The loopback issuer script used for manual local development."""

import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import jwt
import pytest

from agent_template_api.auth import (
    InsufficientScopeError,
    InvalidTokenError,
    TokenValidator,
    fetch_json,
)

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "local_issuer.py"
spec = importlib.util.spec_from_file_location("local_issuer", SCRIPT)
assert spec is not None and spec.loader is not None
local_issuer = importlib.util.module_from_spec(spec)
sys.modules["local_issuer"] = local_issuer
spec.loader.exec_module(local_issuer)

ORIGIN = "http://127.0.0.1:5173"


@pytest.fixture(scope="module")
def issuer() -> Iterator[Any]:
    local = local_issuer.LocalIssuer(port=0, frontend_origin=ORIGIN)
    local.thread.start()
    yield local
    local.server.shutdown()
    local.server.server_close()


def get(
    url: str, origin: str | None = None
) -> tuple[int, dict[str, str], dict[str, Any]]:
    request = Request(url, headers={"Origin": origin} if origin else {})  # noqa: S310
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310
            return response.status, dict(response.headers), json.loads(response.read())
    except HTTPError as error:
        return error.code, dict(error.headers), json.loads(error.read())


def validator(issuer: Any, **overrides: str) -> TokenValidator:
    options = {
        "issuer": issuer.url,
        "discovery_url": issuer.discovery_url,
        "audience": issuer.audience,
        "required_scope": issuer.scope,
    }
    options.update(overrides)
    return TokenValidator(**options, fetcher=fetch_json)


def test_minted_token_is_validated_by_the_production_validator(issuer: Any) -> None:
    status, headers, body = get(f"{issuer.url}/token?subject=dev-1", ORIGIN)

    assert status == 200
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    identity = validator(issuer).validate(body["access_token"])
    assert (identity.issuer, identity.subject) == (issuer.url, "dev-1")


def test_default_subject_is_stable(issuer: Any) -> None:
    first = get(f"{issuer.url}/token")[2]["access_token"]
    second = get(f"{issuer.url}/token")[2]["access_token"]

    claims = [
        jwt.decode(t, options={"verify_signature": False}) for t in (first, second)
    ]
    assert claims[0]["sub"] == claims[1]["sub"]


def test_token_is_rejected_for_another_audience_or_scope(issuer: Any) -> None:
    token = get(f"{issuer.url}/token")[2]["access_token"]

    with pytest.raises(InvalidTokenError):
        validator(issuer, audience="api://other").validate(token)
    with pytest.raises(InsufficientScopeError):
        validator(issuer, required_scope="other.scope").validate(token)


def test_other_origins_cannot_mint_tokens(issuer: Any) -> None:
    status, headers, body = get(f"{issuer.url}/token", "http://evil.example")

    assert status == 403
    assert "Access-Control-Allow-Origin" not in headers
    assert "access_token" not in body


def test_invalid_subject_and_unknown_path_are_rejected(issuer: Any) -> None:
    assert get(f"{issuer.url}/token?subject=a%20b")[0] == 400
    assert get(f"{issuer.url}/nope")[0] == 404


def test_discovery_and_jwks_describe_the_signing_key(issuer: Any) -> None:
    discovery = get(issuer.discovery_url)[2]
    keys = get(discovery["jwks_uri"])[2]["keys"]

    assert discovery["issuer"] == issuer.url
    assert [key["kid"] for key in keys] == [issuer.kid]

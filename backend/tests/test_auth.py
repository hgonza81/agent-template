import time
from typing import Annotated, Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from agent_template_api.auth import (
    IdentityProviderUnavailableError,
    TokenIdentity,
    TokenValidator,
    get_current_identity,
    token_validator_provider,
)

ISSUER = "https://tenant.example.test/tenant-id/v2.0"
DISCOVERY = "https://tenant.example.test/.well-known/openid-configuration"
JWKS_URI = "https://tenant.example.test/keys"
AUDIENCE = "api://agent-template"
SCOPE = "chat.use"


def make_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


KEY = make_key()
OTHER_KEY = make_key()


def jwk(key: rsa.RSAPrivateKey, kid: str) -> dict[str, Any]:
    data: dict[str, Any] = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return {**data, "kid": kid, "use": "sig"}


class Fetcher:
    def __init__(self) -> None:
        self.keys = [jwk(KEY, "k1")]
        self.issuer = ISSUER
        self.calls: list[str] = []
        self.fail = False

    def __call__(self, url: str) -> dict[str, Any]:
        self.calls.append(url)
        if self.fail:
            raise IdentityProviderUnavailableError
        if url == DISCOVERY:
            return {"issuer": self.issuer, "jwks_uri": JWKS_URI}
        return {"keys": self.keys}


def token(
    *,
    key: rsa.RSAPrivateKey | str = KEY,
    kid: str | None = "k1",
    alg: str = "RS256",
    drop: tuple[str, ...] = (),
    **overrides: Any,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-1",
        "exp": now + 600,
        "nbf": now - 10,
        "scp": f"{SCOPE} other",
        "email": "a@example.test",
    }
    claims.update(overrides)
    for name in drop:
        claims.pop(name, None)
    headers = {"kid": kid} if kid else {}
    return jwt.encode(claims, key, algorithm=alg, headers=headers)


@pytest.fixture
def fetcher() -> Fetcher:
    return Fetcher()


@pytest.fixture
def validator(fetcher: Fetcher) -> TokenValidator:
    return TokenValidator(
        issuer=ISSUER,
        discovery_url=DISCOVERY,
        audience=AUDIENCE,
        required_scope=SCOPE,
        fetcher=fetcher,
    )


def test_valid_token_yields_issuer_and_subject(validator: TokenValidator) -> None:
    identity = validator.validate(token())
    assert identity.issuer == ISSUER
    assert identity.subject == "user-1"
    assert SCOPE in identity.scopes
    assert identity.email == "a@example.test"


@pytest.mark.parametrize(
    "bad_token",
    [
        pytest.param("not-a-jwt", id="malformed"),
        pytest.param(token(iss="https://evil.example.test"), id="wrong-issuer"),
        pytest.param(token(aud="api://other"), id="wrong-audience"),
        pytest.param(token(exp=int(time.time()) - 3600), id="expired"),
        pytest.param(token(nbf=int(time.time()) + 3600), id="not-yet-valid"),
        pytest.param(token(drop=("exp",)), id="missing-exp"),
        pytest.param(token(drop=("nbf",)), id="missing-nbf"),
        pytest.param(token(drop=("sub",)), id="missing-sub"),
        pytest.param(token(drop=("aud",)), id="missing-aud"),
        pytest.param(token(drop=("iss",)), id="missing-iss"),
        pytest.param(token(sub=""), id="empty-subject"),
        pytest.param(token(key=OTHER_KEY), id="bad-signature"),
        pytest.param(token(kid="unknown"), id="unknown-kid"),
        pytest.param(token(kid=None), id="missing-kid"),
        pytest.param(token(alg="HS256", key="x" * 64), id="wrong-algorithm"),
        pytest.param(token(scp=["chat.use"]), id="non-string-scope"),
    ],
)
def test_invalid_tokens_are_rejected(validator: TokenValidator, bad_token: str) -> None:
    from agent_template_api.auth import InvalidTokenError

    with pytest.raises(InvalidTokenError):
        validator.validate(bad_token)


def test_alg_none_is_rejected(validator: TokenValidator) -> None:
    from agent_template_api.auth import InvalidTokenError

    unsigned = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "u"},
        "",
        algorithm="none",
        headers={"kid": "k1"},
    )
    with pytest.raises(InvalidTokenError):
        validator.validate(unsigned)


def test_missing_scope_is_insufficient(validator: TokenValidator) -> None:
    from agent_template_api.auth import InsufficientScopeError

    with pytest.raises(InsufficientScopeError):
        validator.validate(token(scp="other"))
    with pytest.raises(InsufficientScopeError):
        validator.validate(token(drop=("scp",)))


def test_scope_must_match_exactly(validator: TokenValidator) -> None:
    from agent_template_api.auth import InsufficientScopeError

    with pytest.raises(InsufficientScopeError):
        validator.validate(token(scp="chat.use.admin"))


def test_jwks_is_cached(validator: TokenValidator, fetcher: Fetcher) -> None:
    validator.validate(token())
    validator.validate(token())
    assert fetcher.calls == [DISCOVERY, JWKS_URI]


def test_key_rotation_refreshes_after_cooldown(fetcher: Fetcher) -> None:
    now = [0.0]
    validator = TokenValidator(
        issuer=ISSUER,
        discovery_url=DISCOVERY,
        audience=AUDIENCE,
        required_scope=SCOPE,
        fetcher=fetcher,
        clock=lambda: now[0],
    )
    validator.validate(token())
    fetcher.keys = [jwk(KEY, "k1"), jwk(OTHER_KEY, "k2")]
    rotated = token(key=OTHER_KEY, kid="k2")

    from agent_template_api.auth import InvalidTokenError

    with pytest.raises(InvalidTokenError):  # within cooldown: no refetch
        validator.validate(rotated)
    assert len(fetcher.calls) == 2
    now[0] = 60
    assert validator.validate(rotated).subject == "user-1"
    assert len(fetcher.calls) == 4


def test_unknown_kid_does_not_refetch_during_cooldown(
    validator: TokenValidator, fetcher: Fetcher
) -> None:
    from agent_template_api.auth import InvalidTokenError

    validator.validate(token())
    for _ in range(5):
        with pytest.raises(InvalidTokenError):
            validator.validate(token(kid="forged"))
    assert len(fetcher.calls) == 2


def test_discovery_issuer_mismatch_is_unavailable(
    validator: TokenValidator, fetcher: Fetcher
) -> None:
    fetcher.issuer = "https://evil.example.test"
    with pytest.raises(IdentityProviderUnavailableError):
        validator.validate(token())


def test_provider_outage_is_unavailable(
    validator: TokenValidator, fetcher: Fetcher
) -> None:
    fetcher.fail = True
    with pytest.raises(IdentityProviderUnavailableError):
        validator.validate(token())


def test_stale_keys_survive_refresh_failure_on_unknown_kid(
    fetcher: Fetcher,
) -> None:
    from agent_template_api.auth import InvalidTokenError

    now = [0.0]
    validator = TokenValidator(
        issuer=ISSUER,
        discovery_url=DISCOVERY,
        audience=AUDIENCE,
        required_scope=SCOPE,
        fetcher=fetcher,
        clock=lambda: now[0],
    )
    validator.validate(token())
    fetcher.fail = True
    now[0] = 60
    with pytest.raises(InvalidTokenError):
        validator.validate(token(kid="other"))
    assert validator.validate(token()).subject == "user-1"


def build_app(validator: TokenValidator | Exception) -> FastAPI:
    app = FastAPI()

    def factory() -> TokenValidator:
        if isinstance(validator, Exception):
            raise validator
        return validator

    app.dependency_overrides[token_validator_provider] = lambda: factory

    @app.get("/protected")
    def protected(
        identity: Annotated[TokenIdentity, Depends(get_current_identity)],
    ) -> dict[str, str]:
        return {"sub": identity.subject}

    return app


def test_dependency_maps_failures_to_http_statuses(
    validator: TokenValidator, fetcher: Fetcher
) -> None:
    client = TestClient(build_app(validator))
    assert client.get("/protected").status_code == 401
    response = client.get("/protected", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401
    response = client.get("/protected", headers={"Authorization": "Bearer junk"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    ok = client.get("/protected", headers={"Authorization": f"Bearer {token()}"})
    assert ok.status_code == 200
    assert ok.json() == {"sub": "user-1"}
    low = client.get(
        "/protected", headers={"Authorization": f"Bearer {token(scp='x')}"}
    )
    assert low.status_code == 403
    fetcher.fail = True
    fresh = TestClient(
        build_app(
            TokenValidator(
                issuer=ISSUER,
                discovery_url=DISCOVERY,
                audience=AUDIENCE,
                required_scope=SCOPE,
                fetcher=fetcher,
            )
        )
    )
    down = fresh.get("/protected", headers={"Authorization": f"Bearer {token()}"})
    assert down.status_code == 503


def test_unconfigured_auth_returns_503() -> None:
    from agent_template_api.auth import AuthNotConfiguredError

    client = TestClient(build_app(AuthNotConfiguredError()))
    response = client.get("/protected", headers={"Authorization": f"Bearer {token()}"})
    assert response.status_code == 503

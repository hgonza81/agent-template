"""Bearer-token validation against OIDC discovery and JWKS metadata."""

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK

logger = logging.getLogger("agent_template_api.auth")
bearer_scheme = HTTPBearer(auto_error=False)

ALLOWED_ALGORITHMS = ["RS256"]
REQUIRED_CLAIMS = ["exp", "nbf", "iss", "aud", "sub"]
FETCH_TIMEOUT_SECONDS = 5
MAX_METADATA_BYTES = 1_000_000


class InvalidTokenError(Exception):
    """The bearer token is missing, malformed, or fails validation."""


class InsufficientScopeError(Exception):
    """The token is valid but lacks the required delegated scope."""


class IdentityProviderUnavailableError(Exception):
    """Discovery or JWKS metadata could not be retrieved or is unusable."""


class AuthNotConfiguredError(Exception):
    """OIDC settings have not been provisioned."""


@dataclass(frozen=True)
class TokenIdentity:
    issuer: str
    subject: str
    scopes: frozenset[str]
    email: str | None = None


JsonFetcher = Callable[[str], dict[str, Any]]


def fetch_json(url: str) -> dict[str, Any]:
    request = UrlRequest(url, headers={"Accept": "application/json"})  # noqa: S310
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310
            body = response.read(MAX_METADATA_BYTES + 1)
        if len(body) > MAX_METADATA_BYTES:
            raise ValueError("metadata too large")
        document = json.loads(body)
    except (OSError, ValueError) as error:
        raise IdentityProviderUnavailableError from error
    if not isinstance(document, dict):
        raise IdentityProviderUnavailableError
    return document


class TokenValidator:
    def __init__(
        self,
        *,
        issuer: str,
        discovery_url: str,
        audience: str,
        required_scope: str,
        fetcher: JsonFetcher = fetch_json,
        jwks_ttl_seconds: float = 3600,
        refresh_cooldown_seconds: float = 30,
        leeway_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._issuer = issuer
        self._discovery_url = discovery_url
        self._audience = audience
        self._required_scope = required_scope
        self._fetcher = fetcher
        self._jwks_ttl = jwks_ttl_seconds
        self._cooldown = refresh_cooldown_seconds
        self._leeway = leeway_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._keys: dict[str, PyJWK] = {}
        self._jwks_uri: str | None = None
        self._fetched_at: float | None = None

    def _refresh(self) -> None:
        discovery = self._fetcher(self._discovery_url)
        if discovery.get("issuer") != self._issuer:
            logger.warning("OIDC discovery issuer does not match configuration")
            raise IdentityProviderUnavailableError
        jwks_uri = discovery.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri.startswith("https://"):
            if not (isinstance(jwks_uri, str) and _is_local_http(jwks_uri)):
                raise IdentityProviderUnavailableError
        document = self._fetcher(jwks_uri)
        raw_keys = document.get("keys")
        if not isinstance(raw_keys, list):
            raise IdentityProviderUnavailableError
        keys: dict[str, PyJWK] = {}
        for raw_key in raw_keys:
            if not isinstance(raw_key, dict):
                continue
            kid = raw_key.get("kid")
            if (
                not isinstance(kid, str)
                or raw_key.get("kty") != "RSA"
                or raw_key.get("use", "sig") != "sig"
            ):
                continue
            try:
                keys[kid] = PyJWK(raw_key)
            except jwt.PyJWTError:
                continue
        if not keys:
            raise IdentityProviderUnavailableError
        self._keys = keys
        self._jwks_uri = jwks_uri
        self._fetched_at = self._clock()

    def _signing_key(self, kid: str) -> PyJWK:
        with self._lock:
            now = self._clock()
            fetched_at = self._fetched_at
            expired = fetched_at is None or now - fetched_at >= self._jwks_ttl
            unknown = kid not in self._keys
            # Unknown kids trigger a refresh (key rotation), rate-limited so
            # forged kids cannot make the API hammer the identity provider.
            cooled_down = fetched_at is None or now - fetched_at >= self._cooldown
            if expired or (unknown and cooled_down):
                try:
                    self._refresh()
                except IdentityProviderUnavailableError:
                    if expired or not self._keys:
                        raise
            key = self._keys.get(kid)
        if key is None:
            raise InvalidTokenError
        return key

    def validate(self, token: str) -> TokenIdentity:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise InvalidTokenError from error
        kid = header.get("kid")
        if header.get("alg") not in ALLOWED_ALGORITHMS or not isinstance(kid, str):
            raise InvalidTokenError
        key = self._signing_key(kid)
        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as error:
            raise InvalidTokenError from error

        subject = claims["sub"]
        if not isinstance(subject, str) or not subject:
            raise InvalidTokenError
        scope_claim = claims.get("scp", "")
        if not isinstance(scope_claim, str):
            raise InvalidTokenError
        scopes = frozenset(scope_claim.split())
        if self._required_scope not in scopes:
            raise InsufficientScopeError
        email = claims.get("email")
        return TokenIdentity(
            issuer=claims["iss"],
            subject=subject,
            scopes=scopes,
            email=email if isinstance(email, str) else None,
        )


def _is_local_http(url: str) -> bool:
    return url.startswith(("http://localhost", "http://127.0.0.1", "http://[::1]"))


_validator_lock = threading.Lock()
_validator: TokenValidator | None = None


def get_token_validator() -> TokenValidator:
    """Return the process-wide validator, built from settings on first use."""
    global _validator
    from agent_template_api.settings import get_settings

    settings = get_settings()
    if (
        settings.oidc_issuer is None
        or settings.oidc_discovery_url is None
        or settings.oidc_audience is None
        or settings.oidc_required_scope is None
    ):
        raise AuthNotConfiguredError
    with _validator_lock:
        if _validator is None:
            _validator = TokenValidator(
                issuer=settings.oidc_issuer,
                discovery_url=str(settings.oidc_discovery_url),
                audience=settings.oidc_audience,
                required_scope=settings.oidc_required_scope,
            )
        return _validator


def token_validator_provider() -> Callable[[], TokenValidator]:
    return get_token_validator


def get_current_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    validator_factory: Annotated[
        Callable[[], TokenValidator], Depends(token_validator_provider)
    ],
) -> TokenIdentity:
    """FastAPI dependency: validated identity from the Authorization header."""
    bearer = {"WWW-Authenticate": "Bearer"}
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, headers=bearer)
    try:
        return validator_factory().validate(credentials.credentials)
    except InvalidTokenError as error:
        raise HTTPException(status_code=401, headers=bearer) from error
    except InsufficientScopeError as error:
        raise HTTPException(status_code=403) from error
    except (AuthNotConfiguredError, IdentityProviderUnavailableError) as error:
        raise HTTPException(status_code=503) from error

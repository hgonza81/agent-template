"""Loopback OIDC issuer for manual local development (no Azure).

Serves OIDC discovery, a JWKS document, and a ``/token`` endpoint that mints
RS256 access tokens signed with a throwaway key generated at startup. Point the
API at it with the OIDC_* values printed on start, and the frontend at it with
VITE_LOCAL_SIGNIN_URL, so the API still validates real signed tokens.

Development only: binds to 127.0.0.1, never persists keys, and must not be
deployed. Run it with ``make local-issuer``.
"""

import argparse
import base64
import hashlib
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

DEFAULT_PORT = 9000
DEFAULT_AUDIENCE = "api://local-dev"
DEFAULT_SCOPE = "chat.use"
DEFAULT_FRONTEND_ORIGIN = "http://127.0.0.1:5173"
TOKEN_LIFETIME_SECONDS = 3600
SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DEFAULT_SUBJECT = "local-dev-user"


class LocalIssuer:
    def __init__(
        self,
        *,
        port: int = DEFAULT_PORT,
        audience: str = DEFAULT_AUDIENCE,
        scope: str = DEFAULT_SCOPE,
        frontend_origin: str = DEFAULT_FRONTEND_ORIGIN,
    ) -> None:
        self.audience = audience
        self.scope = scope
        self.frontend_origin = frontend_origin
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._jwk: dict[str, Any] = dict(
            RSAAlgorithm.to_jwk(self._key.public_key(), as_dict=True)
        )
        digest = hashlib.sha256(json.dumps(self._jwk, sort_keys=True).encode()).digest()
        # A new key on every start gets a new kid, so the API refreshes its JWKS.
        self.kid = base64.urlsafe_b64encode(digest[:9]).decode()
        self._jwk.update({"kid": self.kid, "use": "sig", "alg": "RS256"})
        issuer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                issuer.handle(self)

            def do_OPTIONS(self) -> None:  # noqa: N802
                issuer.respond(self, 204, None)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    @property
    def discovery_url(self) -> str:
        return f"{self.url}/.well-known/openid-configuration"

    def mint(self, subject: str) -> str:
        now = int(time.time())
        claims = {
            "iss": self.url,
            "aud": self.audience,
            "sub": subject,
            "exp": now + TOKEN_LIFETIME_SECONDS,
            "nbf": now - 5,
            "scp": self.scope,
            "name": "Local Developer",
            "email": f"{subject}@example.test",
        }
        return jwt.encode(
            claims, self._key, algorithm="RS256", headers={"kid": self.kid}
        )

    def respond(
        self, handler: BaseHTTPRequestHandler, status: int, body: Any | None
    ) -> None:
        payload = b"" if body is None else json.dumps(body).encode()
        handler.send_response(status)
        origin = handler.headers.get("Origin")
        if origin == self.frontend_origin:
            handler.send_header("Access-Control-Allow-Origin", origin)
            handler.send_header("Vary", "Origin")
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)

    def handle(self, handler: BaseHTTPRequestHandler) -> None:
        parts = urlsplit(handler.path)
        if parts.path == "/.well-known/openid-configuration":
            self.respond(
                handler, 200, {"issuer": self.url, "jwks_uri": f"{self.url}/keys"}
            )
        elif parts.path == "/keys":
            self.respond(handler, 200, {"keys": [self._jwk]})
        elif parts.path == "/token":
            origin = handler.headers.get("Origin")
            if origin is not None and origin != self.frontend_origin:
                self.respond(handler, 403, {"error": "origin not allowed"})
                return
            subject = parse_qs(parts.query).get("subject", [DEFAULT_SUBJECT])[0]
            if not SUBJECT_PATTERN.fullmatch(subject):
                self.respond(handler, 400, {"error": "invalid subject"})
                return
            self.respond(
                handler,
                200,
                {
                    "access_token": self.mint(subject),
                    "name": "Local Developer",
                    "expires_in": TOKEN_LIFETIME_SECONDS,
                },
            )
        else:
            self.respond(handler, 404, {"error": "not found"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--audience", default=DEFAULT_AUDIENCE)
    parser.add_argument("--scope", default=DEFAULT_SCOPE)
    parser.add_argument("--frontend-origin", default=DEFAULT_FRONTEND_ORIGIN)
    args = parser.parse_args()
    issuer = LocalIssuer(
        port=args.port,
        audience=args.audience,
        scope=args.scope,
        frontend_origin=args.frontend_origin,
    )
    print(  # noqa: T201
        "Local OIDC issuer (development only). Set in backend/.env and restart "
        "the API:\n"
        f"  OIDC_ISSUER={issuer.url}\n"
        f"  OIDC_DISCOVERY_URL={issuer.discovery_url}\n"
        f"  OIDC_AUDIENCE={issuer.audience}\n"
        f"  OIDC_REQUIRED_SCOPE={issuer.scope}\n"
        "Set in frontend/.env and restart the frontend:\n"
        f"  VITE_LOCAL_SIGNIN_URL={issuer.url}\n"
        "Press Ctrl+C to stop.",
        flush=True,
    )
    try:
        issuer.server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        issuer.server.server_close()


if __name__ == "__main__":
    main()

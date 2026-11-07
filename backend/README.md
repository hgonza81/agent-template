# Agent Template API

Run the following commands from the repository root. Start with `make setup`
to create local environment files and install the backend and frontend
dependencies. Docker Desktop (or another Docker engine with Compose) must be
running.

Start the API with `make backend`. It starts PostgreSQL, applies pending
migrations, and launches the development server. The API is available at
`http://127.0.0.1:8000`; interactive OpenAPI documentation is at `/docs`.
Start the frontend separately with `make frontend`.

The liveness endpoint (`/api/v1/health/live`) checks that the process is
running without contacting dependencies. The readiness endpoint
(`/api/v1/health/ready`) returns `503` when PostgreSQL is unavailable.

API request logs are JSON events containing the request ID, HTTP method, route
template, status code, and duration. They do not include raw request paths,
query strings, headers, bodies, or exception messages. Responses include the
`X-Request-ID` header, which is exposed to browser clients by CORS; error
responses also include that ID in their JSON body and use generic messages
rather than exception details. `make backend` disables Uvicorn's raw access
logs so they do not duplicate or expose request-line data.
Set `LOG_LEVEL` in `backend/.env` to `DEBUG`, `INFO` (the default), `WARNING`,
`ERROR`, or `CRITICAL` to control API request log verbosity; values are
case-insensitive.

## Optional local traces and metrics

OpenTelemetry instrumentation is disabled unless
`OTEL_EXPORTER_OTLP_ENDPOINT` is configured. To start the local OTLP collector,
Jaeger trace viewer, and Prometheus metrics viewer, run from the repository
root:

```bash
make observability-up
```

The observability profile is optional: the regular `make backend` workflow
starts PostgreSQL only and does not start these services or require a hosted
monitoring account. The three pinned images currently total about 900 MB to
download, so leave at least 1 GB of free Docker storage for their initial
pull. Compose does not impose CPU or memory limits; usage depends on local
traffic and how long the tools retain data, so allocate additional Docker
resources if the stack is under sustained use.

In another terminal, run `make backend-otel` to start the API with OTLP
export enabled. Open Jaeger at `http://127.0.0.1:16686` to inspect traces and
Prometheus at `http://127.0.0.1:9090` to query metrics such as
`http_server_duration_milliseconds_count`. Stop only the optional telemetry
services with `make observability-down`; `make db-down` also stops all Compose
services without deleting persisted database data.

The API instruments HTTP requests and SQLAlchemy operations. Before exporting,
span attributes and metric labels are allowlisted; URLs, raw request paths,
query strings, SQL statements, exception events, and exception descriptions
are omitted. Trace route attributes use route templates. No telemetry leaves
the machine unless an OTLP endpoint is explicitly configured. Stop the
optional telemetry containers with `make observability-down`; `make db-down`
stops the default Compose services and preserves the database volume.

## OpenAPI contract

FastAPI defines the API contract. After changing backend routes or models, run
`make openapi` to update `openapi/openapi.json`. Run `make api-types` to also
regenerate the frontend types. Commit both generated files; do not edit the
frontend generated file by hand.

## Local PostgreSQL

PostgreSQL runs in Docker Compose and binds only to `127.0.0.1:5433` on your
computer (container port `5432`). `make backend`, `make test-backend`, and
`make migrate` start it and wait for its health check automatically. The
container creates the application database (`agent_template`) and a separate
test database (`agent_template_test`) on first start. The local-only
credentials are defined in `compose.yaml`; the named volume preserves data
when the service is stopped.

After adding a model, create a migration with
`make migration MESSAGE="describe the schema change"`. Review the generated
migration before applying it with `make migrate`. Each schema change is
committed with its model and migration.

The `subscriptions` table stores a UUID, the validated issuer/subject identity
pair, an optional email snapshot, a UTC-aware start time, and an optional
server-managed Foundry thread ID. The issuer/subject pair has a database
uniqueness constraint; `started_at` defaults to UTC-aware application time or
the database's current timestamp, and connections use the UTC time zone.

Run backend tests with `make test-backend`, or run both backend and frontend
tests with `make test`. The integration tests use only `agent_template_test`
and verify uniqueness, UUID generation, UTC timestamps, and migrations.

`make db-reset-test` recreates only the test database and reapplies migrations;
all data in that database will be deleted. Stop PostgreSQL and preserve its
data with `make db-down`. Do not remove the Compose volume unless you intend to
delete both local databases and all their data.

## Quality checks

Run `make check-backend` for Python formatting, lint, and type checks;
`make check` runs the full test suite and frontend checks as well. Run
`make audit` to scan Python and npm dependencies.

## Token validation (Entra External ID)

`agent_template_api.auth` validates bearer access tokens. Routes opt in with
`Depends(get_current_identity)`, which yields the validated issuer and subject.
It discovers the signing keys through the OIDC discovery document, checks that
the document's `issuer` matches `OIDC_ISSUER`, and caches the JWKS for an
hour. An unknown `kid` triggers a refresh (key rotation), at most once every
30 seconds. Only RS256 is accepted, and the signature, `iss`, `aud`, `exp`,
`nbf`, and `sub` claims are required (30 seconds of clock leeway). The `scp`
claim must contain `OIDC_REQUIRED_SCOPE` as an exact entry.

Failures map to `401` (missing or invalid token, with `WWW-Authenticate:
Bearer`), `403` (valid token, missing scope), and `503` (identity provider
unreachable or auth not configured). Responses never describe why a token
failed. Tenant values are pending provisioning: leave the four `OIDC_*`
variables blank in `backend/.env` (auth routes return `503`) or set all four.
Tests use locally generated keys and never contact a real tenant.

## Subscription provisioning

`GET /api/v1/me/subscription` requires a valid bearer token and returns the
caller's free subscription (`id`, `started_at`, `email`), creating it on the
first call. Identity is the validated `(issuer, subject)` pair only; the
request has no body and query/header values are ignored. Creation is a single
`INSERT ... ON CONFLICT DO NOTHING` on the unique identity constraint followed
by a read in the same transaction, so retries and concurrent first requests
return the same row. The response never includes the issuer, subject, or
Foundry thread ID. The email is a normalized display snapshot written at
creation and refreshed under the policy below.

### Email policy

Email is display/contact data only. Accounts are looked up exclusively by
`(issuer, subject)`; no query, index, or constraint involves email, and it never
authorizes anything. A valid, different email claim updates the stored
snapshot in place (no new subscription); a missing or invalid claim keeps the
existing snapshot. Two identities sharing an email get separate subscriptions.

## Test identity strategy

Local and CI tests never use a real tenant or credentials. Backend flow tests
(`tests/test_local_identity_flow.py`) mint tokens with a throwaway RSA key and
validate them with the production `TokenValidator` and HTTP fetcher against a
loopback OIDC discovery/JWKS server. Frontend flow tests
(`frontend/src/flow.test.tsx`) drive the real UI with an in-memory fake sign-in
(`src/testing/FakeAuthProvider.tsx`) and a stubbed `fetch`, which is not
imported by the application bundle. Use real Entra External ID only for manual
acceptance checks once the tenant and app registrations are provisioned.

## Chat agent interface

`agent_template_api.agent` defines the server-side `ChatAgent` protocol
(`create_thread`, `send_message`), the content-free `AgentError` family, and a
deterministic in-memory `FakeChatAgent` so local work and tests need no Azure.
It is a plain agent: no persona/system prompt, tools, or retrieval.
`AGENT_PROVIDER=fake` (the default) selects the fake; the Foundry adapter will
add a second value later. The fake replies `Fake reply N: <message>` and
supports injected delays and failures for timeout, error, and cancellation
tests. Routes depend on the protocol only (`get_chat_agent`).

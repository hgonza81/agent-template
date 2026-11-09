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

## Azure Monitor / Application Insights export

Setting `APPLICATIONINSIGHTS_CONNECTION_STRING` (a secret: it carries the
instrumentation key; blank counts as unset) exports the same traces and HTTP
and database metrics to Application Insights through the
`azure-monitor-opentelemetry-exporter`. It can run next to the optional OTLP
export; with neither variable set, telemetry stays off. Both go through the
same allowlist described above, so route templates and status codes are
exported but chat content, prompts, model output, tokens, URLs, SQL, and
exception details never are. Statsbeat (Microsoft SDK self-telemetry) and
on-disk offline storage of telemetry are disabled. In `dev` Terraform sets the
variable from a Container Apps secret. Retention is 30 days with a 0.1 GB/day
cap (see `infra/terraform/README.md`). Tests use a fake exporter, no network.
The trace exporter is given the app's own `TracerProvider` so it can read the
service resource; otherwise it falls back to the global (resource-less) provider
and logs `ProxyTracerProvider has no attribute resource` on every export.

## Diagnosing provider failures

When the provider call fails the API still answers with the generic `503`/`504`
(`detail` + `request_id`), but the `api.request` log line (and the request span's
`provider.error_type` / `provider.status_code` attributes) also carry
`provider_error_type` (the exception class name, e.g. `AuthenticationError`,
`PermissionDeniedError`, `NotFoundError`, `ClientAuthenticationError`,
`CredentialUnavailableError`) and `provider_status` (HTTP status, when the
exception has one). Nothing else from the exception (message, body, headers) is
recorded, since it may echo chat content or tokens. Credential errors from
`DefaultAzureCredential` are classified the same way.

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

Migration compatibility is checked by `tests/test_migrations.py`, which uses
throwaway databases (never your development data) to verify a single Alembic
head, upgrade from an empty database, no drift between models and migrations,
and a downgrade to base followed by a fresh upgrade. Keep each migration
reversible and commit it with the model change.

To safely reset test data, run `make db-reset-test`. It recreates only
`agent_template_test` and reapplies migrations;
all data in that database will be deleted. Stop PostgreSQL and preserve its
data with `make db-down`. Do not remove the Compose volume unless you intend to
delete both local databases and all their data.

## Supabase PostgreSQL (ADR 0005)

Verified on 2026-11-08 against a free-plan Supabase project (PostgreSQL 17):
`alembic upgrade head` applies cleanly, and with the fake agent and the local
issuer, subscription provisioning, chat, `DELETE /api/v1/me`, and isolation
between two identities all behave as locally. The test suite is never run
against Supabase.

- Keep the connection string in an ignored file (`backend/.env.supabase`) or in
  deployment secrets; never commit or log it. Load it only into the process
  environment, e.g. `set -a; . backend/.env.supabase; set +a`.
- Driver URL form: `postgresql+psycopg://postgres:<password>@<host>:5432/postgres`.
- TLS: the server offers TLS and libpq negotiates it by default; append
  `?sslmode=require` to the URL to make it mandatory (works, no code change).
- Direct connection (`db.<ref>.supabase.co:5432`) is IPv6 only. It works from
  machines with IPv6; the migrations and API run fine over it.
- Session pooler (`aws-0-<region>.pooler.supabase.com:5432`, user
  `postgres.<ref>`) accepts IPv4 and connects with `sslmode=require`; use it
  where IPv6 egress is missing (probably Azure). Use session mode (port 5432),
  not transaction mode (6543). Pending: confirm it from the actual Azure host in
  Phase B, and re-run migrations through it once.
- Remove test rows afterwards (`DELETE /api/v1/me` per identity); migrated
  tables can stay.

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
`AGENT_PROVIDER=fake` (the default) selects the fake. The fake replies `Fake reply N: <message>` and
supports injected delays and failures for timeout, error, and cancellation
tests. Routes depend on the protocol only (`get_chat_agent`).

### Live Foundry (opt-in)

`AGENT_PROVIDER=foundry` calls the real Azure AI Foundry model deployment
(Conversations + Responses APIs on the OpenAI-compatible endpoint) with
`DefaultAzureCredential`: your `az login` locally, the managed identity in
Azure. No keys or secrets. Requires the Foundry User role on the project.
`FOUNDRY_PROJECT_ENDPOINT` (HTTPS) and `FOUNDRY_DEPLOYMENT` are mandatory in this mode;
if either is missing the API fails at startup (it never falls back to the
fake). Dev values: project endpoint `https://ai-agent-template-dev.services.ai.azure.com/api/projects/proj-agent-template-dev`
(centralus), deployment `chat`
(`gpt-5.4-nano`). Start locally:

```sh
az login
AGENT_PROVIDER=foundry \
FOUNDRY_PROJECT_ENDPOINT=https://ai-agent-template-dev.services.ai.azure.com/api/projects/proj-agent-template-dev \
FOUNDRY_DEPLOYMENT=chat make backend
```

Requests send only the user message; no instructions, tools, or retrieval.
Tests never call Foundry (a mock client is used); the live path is verified
manually.

## Chat endpoint

`POST /api/v1/chat/messages` takes `{"message": "..."}` and returns
`{"reply": "..."}`. It requires a valid bearer token, provisions the caller's
subscription if needed, resolves (or creates and stores) the subscription's
single provider thread, and sends the message through the `ChatAgent`. The
request model forbids extra fields, so user, subscription, agent, and thread
identifiers cannot be supplied. Provider and database failures return a generic
`503`. Message content is never logged.

### Conversation thread creation

The first message locks the subscription row (`SELECT ... FOR UPDATE`) while the
provider thread is created and its reference stored in one transaction, so
concurrent first messages create exactly one thread and later requests use an
unlocked read. A failed provider call or commit stores nothing and the next
request retries. The thread reference is server-only: it is never returned or
accepted from a client, and each lookup is scoped by the subscription derived
from the validated identity. Known limit: a provider thread created just
before a failed commit is orphaned; the Foundry adapter should handle cleanup
if the provider supports deletion.

### Account deletion

`DELETE /api/v1/me` (valid bearer token) deletes the caller's own account and
returns `204` with no body. The target is always the validated
(issuer, subject); nothing from the request selects it. It locks the
subscription row, deletes the provider conversation (a provider `404` counts as
already deleted), and only then deletes the row. If the provider call fails the
row and its thread reference are kept and the response is a generic `503`
(`504` on timeout), so retrying is safe and no conversation is left orphaned.
Deleting an account that no longer exists is a no-op `204`. Chat content is
never stored in PostgreSQL, so nothing else needs deleting; a new sign-in
afterwards provisions a fresh subscription.

### Chat limits and failure handling

| Control | Setting (default) | Result when exceeded |
|---|---|---|
| Message size | `CHAT_MAX_MESSAGE_CHARS` (4000) | `422` (also in OpenAPI as `maxLength`) |
| Rate per subscription | `CHAT_RATE_LIMIT_PER_MINUTE` (20) | `429` + `Retry-After` |
| In-flight requests | `CHAT_MAX_CONCURRENT_REQUESTS` (5) | `429` + `Retry-After: 1` |
| Agent timeout | `CHAT_TIMEOUT_SECONDS` (30) | `504` |

Provider failures return a generic `503`, provider timeouts `504`. Errors carry
only `detail` and `request_id`, never message or provider text. If the client
disconnects or the request is cancelled, the agent call is cancelled and the
concurrency slot and thread-creation row lock are released; the provider may
still have recorded a message that was already being sent. The rate and
concurrency limiters are in-memory per API process, so size them per instance
(or add a shared store) when scaling out. Retrying after a timeout or failure
is safe: no thread reference is stored for a failed creation.

### End-to-end local chat tests

`tests/test_chat_e2e.py` runs the whole path with no Azure: tokens from the
loopback OIDC issuer are validated by the production validator, the real test
database stores subscriptions and thread references, and `FakeChatAgent`
answers. It proves a user keeps one persistent conversation, that two users get
separate threads and histories (including interleaved messages), that supplying
another user's thread, subscription, user, or agent ID is rejected with `422`
without touching their conversation, and that missing or under-scoped tokens
never reach the agent.

## Conversation retention and deletion

Behavior today:

- Chat content lives only in the Foundry conversation (ADR 0003). PostgreSQL
  holds only the opaque conversation reference on `subscriptions`.
- The conversation is kept while the account is active; there is no reset.
- The backend has no account-deletion endpoint and the `FoundryClient` has no
  delete method yet. Deleting a `subscriptions` row today would orphan the
  provider conversation. Account deletion (spec: delete the subscription and
  its Foundry thread) is therefore not implemented; it must call
  `conversations.delete` first and then remove the row.
- A conversation created just before a failed commit is also orphaned (see
  "Conversation thread creation").

Verified live on 2026-11-08 against the dev project, with no model calls (no
tokens used), using the installed `openai` SDK 2.54.0 (`conversations.delete`
exists) and `az login`: create a conversation, retrieve it, delete it
(`deleted: true`), then retrieve again returned `404` and deleting again
returned `404`. So deletion by the API is immediate from the caller's point of
view and a deleted conversation can no longer be read through the API.
Deletion is idempotent-safe if a `404` is treated as already deleted.

Not verified (cannot be observed through the API):

- Whether Microsoft keeps the data after deletion (backups, abuse monitoring
  retention, or replicas) and for how long.
- Retention of stored responses (`store=True` is sent) and whether deleting a
  conversation also removes the responses created in it.
- Data-handling terms of the deployment type (Global/DataZone Standard) and
  data residency for stored conversation state.
- Behavior at scale or with long histories; only an empty conversation was
  deleted.

Sources to review before launch (not re-fetched in this verification):
Microsoft Learn, "Data, privacy, and security for Azure Direct Models in
Microsoft Foundry" (https://learn.microsoft.com/azure/foundry/responsible-ai/openai/data-privacy)
and the Foundry/Azure OpenAI Responses and Conversations API reference
(https://learn.microsoft.com/azure/foundry/openai/how-to/responses). The user
privacy notice must disclose the unverified points above, as spec.md requires.

## Foundry provider decision (pending provisioning)

Status: proposed and documented only. Nothing is provisioned, no Azure call is
made, and no credentials exist. Live Foundry calls stay disabled (the
deterministic fake agent is used) until provisioning is explicitly approved.

| Item | Decision |
| --- | --- |
| Provider | Azure AI Foundry Agent Service, called server-side with managed identity |
| Region | South Central US (San Antonio, Texas), the closest Azure region to Houston. Fallback: East US 2 |
| Model | `gpt-4.1-nano` (Global Standard deployment), the cheapest adequate model for plain chat. Fallback: `gpt-4o-mini` |
| Agent config | Only provider-required settings: no system prompt, tools, retrieval, or custom guardrails |
| Quotas | Default minimum quotas for the subscription; no increase requests |
| Budget | USD 10/month for Azure, below the USD 50 dev/staging ceiling in the spec |
| Data handling | Foundry owns thread history; chat content never goes to logs or telemetry; retention/deletion is verified before production |

Region and model availability could not be verified from this environment
(offline, no Azure access). Before provisioning, confirm in the Azure
portal/docs that South Central US offers Foundry Agent Service and the
`gpt-4.1-nano` deployment under the subscription's default quota, and
re-check current prices. If not, use the fallbacks and re-review.

### Cost estimate (model usage only, approximate list prices to re-verify)

Assumption: 1,000 messages/month, about 2,000 input tokens (thread history
included) and 300 output tokens each, at roughly USD 0.10 per 1M input and
USD 0.40 per 1M output tokens: 2M x 0.10 + 0.3M x 0.40, about USD 0.32/month.
Even with 10x the usage this stays near USD 3.20/month, within the budget.

Open point: the USD 10/month budget must cover the whole stack, not just the
model. A managed PostgreSQL instance, Container Apps, registry, and monitoring
may alone exceed it. Itemize them before provisioning; if the total exceeds
USD 10, request explicit approval of a revised ceiling (still within USD 50).
Budgets and alerts are not hard spending caps, so keep the application token
and rate limits enabled.

## Foundry adapter

`agent_template_api.foundry_agent.FoundryChatAgent` implements `ChatAgent` on
top of an injected `FoundryClient` (`create_thread`, `run_message`), so it has
no SDK, credentials, or live Azure calls yet and is tested with a mock client.
Provider calls stay server-side; only the user text, the server-owned thread
reference, and the configured agent ID are passed. Provider failures map to the
content-free `AgentTimeoutError`, `AgentThreadNotFoundError`, and
`AgentUnavailableError` (the original exception is dropped), cancellation
propagates, and the adapter never logs or records prompts, messages, or output.
It is not selectable via `AGENT_PROVIDER` until the live client is wired in
Phase 7b.

In Azure, migrations run in the manual Container Apps job from the API image
(`alembic -c alembic.ini upgrade head`, ADR 0017); see `infra/terraform/README.md`.

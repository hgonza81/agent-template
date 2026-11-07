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

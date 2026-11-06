# Agent Template API

From the repository root, install the pinned Python runtime and start the API:

```bash
uv python install 3.13
cd backend
cp .env.example .env
uv sync --frozen
uv run uvicorn agent_template_api.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `/docs`. 

## OpenAPI contract

FastAPI defines the API contract. Export the current schema after changing backend
routes or models:

```bash
uv run python -m agent_template_api.export_openapi
```

This updates the checked-in `../openapi/openapi.json` contract.

## Local PostgreSQL

PostgreSQL runs in Docker Compose. Docker Desktop (or another Docker engine with Compose) must be running. From the repository root, start the database and wait for its health check:

```bash
docker compose up -d --wait postgres
```

The service binds only to `127.0.0.1:5433` on your computer (container port `5432`).
It creates an application database (`agent_template`) and a separate test database (`agent_template_test`) on the first start. These databases use disposable local-only credentials defined in `compose.yaml`. The named volume preserves data when the service is stopped.

Copy `backend/.env.example` to `backend/.env`, then run the initial migration
and start the API from `backend/`:

```bash
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn agent_template_api.main:app --reload
```

After adding a model, create a migration with
`uv run alembic revision --autogenerate -m "describe the schema change"`.
Review the generated migration before applying it with `uv run alembic upgrade head`.
Each schema change is committed with its model and migration.
The `subscriptions` table stores a UUID, the validated issuer/subject identity
pair, an optional email snapshot, a UTC-aware start time, and an optional
server-managed Foundry thread ID. The issuer/subject pair has a database
uniqueness constraint; `started_at` defaults to UTC-aware application time or
the database's current timestamp, and connections use the UTC time zone.

Run the backend tests against the separate test database by overriding the
connection URL. The subscription model integration tests verify uniqueness,
UUID generation, UTC timestamps, and apply pending Alembic migrations:

```bash
DATABASE_URL=postgresql+psycopg://agent_template:local-dev-only@127.0.0.1:5433/agent_template_test uv run pytest
```

To reset only the test database:

```bash
docker compose exec -T postgres dropdb --if-exists -U agent_template agent_template_test
docker compose exec -T postgres createdb -U agent_template --owner=agent_template agent_template_test
DATABASE_URL=postgresql+psycopg://agent_template:local-dev-only@127.0.0.1:5433/agent_template_test uv run alembic upgrade head
```

Stop PostgreSQL and preserve both databases with `docker compose down`. To
delete the local databases and all their data, use `docker compose down --volumes`
and start again with `docker compose up -d --wait postgres`; the initialization
script recreates the test database only when the data volume is empty.

## Quality checks

Run these commands from `backend/` after `uv sync --frozen`:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv export --locked --format requirements.txt --no-emit-project \
  --output-file "${TMPDIR:-/tmp}/agent-template-backend-requirements.txt"
uv run pip-audit --strict --require-hashes \
  --requirement "${TMPDIR:-/tmp}/agent-template-backend-requirements.txt"
```
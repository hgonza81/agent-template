# Agent Template

A plain chat agent behind sign-in: one free subscription per person and one
persistent conversation per subscription. See
[`specs/agent-template/spec.md`](specs/agent-template/spec.md) and
[`plan.md`](specs/agent-template/plan.md).

## Local workflow (no Azure required)

Prerequisites: Python 3.13 with `uv`, Node 24 (`.nvmrc`), and Docker running.
Run everything from the repository root.

1. `make setup` creates `backend/.env` and `frontend/.env` from the examples
   and installs dependencies. Leave `OIDC_*` / `VITE_ENTRA_*` blank locally;
   `AGENT_PROVIDER=fake` (the default) uses the deterministic fake agent.
2. `make backend` starts PostgreSQL (Docker), applies migrations, and serves
   the API at `http://127.0.0.1:8000` (docs at `/docs`).
3. `make frontend` serves the UI at `http://127.0.0.1:5173`.
4. Check the API: `GET /api/v1/health/live` and `/api/v1/health/ready` should
   both return `{"status":"ok"}`.

Optional telemetry: `make backend-otel` (instead of `make backend`) also starts
a local collector, Prometheus, and Jaeger; stop them with
`make observability-down`. Telemetry never contains chat content or
credentials. See [`backend/README.md`](backend/README.md).

Other commands: `make test`, `make check` (run before committing),
`make db-reset-test`, `make db-down`, `make api-types` after API changes.
Run `make help` for the full list.

## Container images

`backend/Dockerfile` (API) and `frontend/Dockerfile` (static SPA on nginx) build
reproducible images: base images pinned by digest, dependencies installed from
`uv.lock` / `package-lock.json`, and a non-root runtime user. Both define a
`HEALTHCHECK` (API: `/api/v1/health/live`, which never touches the database or
provider; web: `/healthz`) and stop gracefully on `SIGTERM` (uvicorn drains
in-flight requests for up to 25 seconds).

- `make docker-build` builds `agent-template-api:local` and
  `agent-template-web:local`.
- `make docker-test` builds both and verifies non-root users, health, liveness
  versus readiness without a database, SPA fallback, and graceful shutdown.
- The API reads its configuration from environment variables at runtime
  (`DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `OIDC_*`); no `.env` file is baked
  in. Run migrations with `alembic upgrade head` inside the API image.
- `VITE_*` values are public and baked into the web image at build time via
  `--build-arg` (for example `VITE_API_BASE_URL`).

## Local verification record

Full local suite run before starting cloud infrastructure work (no Azure used):

| Command | Result |
| --- | --- |
| `make check` | Passed: backend format/lint/types, 136 backend tests, 67 frontend tests, frontend lint/typecheck/build |
| `make audit` | Passed: no known Python or npm vulnerabilities |
| `make docker-test` | Passed: non-root, health checks, graceful shutdown |

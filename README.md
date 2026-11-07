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

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

### Try the chat locally with sign-in (no Azure)

Opt-in, development only. The API still validates real signed tokens; they
come from a loopback issuer script instead of Entra.

1. `make local-issuer` starts the issuer on `http://127.0.0.1:9000` and prints
   the values to use.
2. Set `OIDC_ISSUER`, `OIDC_DISCOVERY_URL`, `OIDC_AUDIENCE`, and
   `OIDC_REQUIRED_SCOPE` in `backend/.env` (defaults: `http://127.0.0.1:9000`,
   `.../.well-known/openid-configuration`, `api://local-dev`, `chat.use`), then
   `make backend`.
3. Set `VITE_LOCAL_SIGNIN_URL=http://127.0.0.1:9000` in `frontend/.env` (leave
   `VITE_ENTRA_*` blank), then `make frontend`. **Sign in** now reaches the
   chat with the fake agent.

The issuer generates a throwaway key on each start (restarting it gives new
tokens), binds to loopback only, and only hands tokens to the frontend origin.
`npm run build` fails if `VITE_LOCAL_SIGNIN_URL` is set, so it cannot ship.
Revert the blank values to go back to the default local setup.

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

## Dev deployment verification (ADR 0018)

Every push to `main` that passes CI runs the `deploy` job: it migrates, updates
the dev apps to the published digests and runs automated smoke tests (API
liveness/readiness, web `/` and `/healthz`, and a 401 without a token). If
anything fails, the job restores the previous images (migrations are not
reverted). To roll back by hand:
`az containerapp update -g rg-agent-template-dev -n <app> --image <previous digest>`.
See [`docs/operations.md`](docs/operations.md) for rollback, migration
recovery, deployment provenance, and troubleshooting.

Sign-up, subscription provisioning and chat need a real Entra External ID user
and are checked manually after each deployment:

1. Open the web app URL and sign up with a new email (or sign in).
2. Confirm the app shows the free subscription for that account (provisioned on
   first sign-in; a second sign-in must not create another).
3. Send a message and confirm a reply, reload and confirm the conversation
   persists.
4. Sign out and confirm the chat is no longer reachable.

## Local verification record

Full local suite run before starting cloud infrastructure work (no Azure used):

| Command | Result |
| --- | --- |
| `make check` | Passed: backend format/lint/types, 136 backend tests, 67 frontend tests, frontend lint/typecheck/build |
| `make audit` | Passed: no known Python or npm vulnerabilities |
| `make docker-test` | Passed: non-root, health checks, graceful shutdown |

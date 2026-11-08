# Agent instructions

## Project

Agent Template: a plain chat agent behind sign-in. One free subscription per
person and one persistent conversation per subscription.

- Stack: Python 3.13 + FastAPI + SQLAlchemy/Alembic + PostgreSQL (`backend/`),
  React + TypeScript + Vite + MUI + MSAL (`frontend/`), Entra External ID for
  identity, Azure AI Foundry as the future provider (a deterministic fake agent
  is used until then).
- Specification: [`specs/agent-template/spec.md`](specs/agent-template/spec.md),
  design: [`plan.md`](specs/agent-template/plan.md).
- Tasks: [`specs/agent-template/tasks.md`](specs/agent-template/tasks.md) is the
  ordered implementation checklist.
- Runtimes: Python 3.13 (`uv`, lockfile `backend/uv.lock`), Node 24
  (`.nvmrc`, `frontend/package-lock.json`). Docker is required for PostgreSQL.

## Commands

Run from the repository root.

- Setup: `make setup`
- Run API: `make backend` (starts PostgreSQL, migrates); frontend: `make frontend`
- Tests: `make test` (`make test-backend`, `make test-frontend`)
- Lint, types, build: `make check-backend`, `make check-frontend`
- Everything before committing: `make check`
- Dependency audit: `make audit`
- After changing API routes or models: `make api-types` (regenerates
  `openapi/openapi.json` and `frontend/src/generated/Api.ts`; commit both and
  never edit the generated file by hand)
- Migrations: `make migration MESSAGE="..."`, `make migrate`;
  reset test data: `make db-reset-test`

## Workflow

- Work through `tasks.md` in order. One task item = one commit, made right after
  its acceptance checks pass. Keep commits scoped to the task; no unrelated work.
- Do not mark a task `[x]` until its checks pass and its commit exists. Tick the
  box in the same commit.
- Commit subject: the task's wording, imperative, e.g. `Add bounded message size
  ...` (no `T-XX` ids exist in `tasks.md`). Add a body when it helps.
- Solo repository: commit directly to `main`, no branches or PRs. Do not
  `git push` unless asked.
- Do not edit `spec.md` or `plan.md` unless the user asks; `tasks.md` only to
  tick completed items (or when the user changes the plan).
- Do not add dependencies unless the task requires them; pin them via the
  lockfile (`uv add`, `npm install`) and keep `make audit` clean.
- Stop when the user says to stop; do not start the next task on your own
  initiative if told to pause.
- Record every significant decision (hard to reverse, changes the design, costs
  money, moves something outside Azure, or settles a real dilemma) as an ADR in
  [`docs/adr/`](docs/adr/README.md), in the same commit as the change it
  explains. Read the existing ADRs before deciding; to change a decision, add a
  new ADR that supersedes the old one.
- When a dilemma has several acceptable options, pick the simplest decent one
  and improve it later if needed. This is an incremental project: do not
  over-engineer or build for hypothetical needs, and say so in the ADR when you
  chose simple over complete.

## Conventions

- Cloud-free until the explicit Azure gates in `tasks.md` (Phase 7+): no Azure
  provisioning, credentials, or paid calls without explicit approval.
  Azure budget and hosting rules (USD 10/month cap, avoid fixed costs, Foundry
  stays on Azure, flag high fixed costs before creating them) are in
  [ADR 0002](docs/adr/0002-single-dev-environment-on-azure-within-a-usd-10-budget.md).
- Never commit secrets, `.env` files, local databases, Terraform state, or plan
  files. Only `*.env.example` files are tracked.
- Privacy: never log or put in telemetry tokens, credentials, chat content, or
  unnecessary personal data. Error responses are generic (`detail` +
  `request_id`) and never leak exceptions or configuration.
- Identity is the validated `(issuer, subject)` pair only. Email is display data;
  never look up, merge, or authorize by email. Client input must never supply
  user, subscription, agent, or provider-thread IDs.
- Authorization is enforced in FastAPI; frontend route guards are UX only.
- Plain agent: no custom persona/system prompt, tools, retrieval, or
  orchestration.
- Backend: strict mypy, ruff (format + lint); frontend: oxlint with
  `--deny-warnings`, strict TypeScript. Document user-visible behavior in
  `backend/README.md` / `frontend/README.md`.
- Tests prove behavior: add or update tests with every change, including
  failure and authorization-boundary cases.

## Gotchas

- Backend tests need PostgreSQL (`make test-backend` starts it) and must use the
  `agent_template_test` database. Never call `get_settings()` in a test
  without setting env first: it is cached and would bind later tests to the dev
  database. Build `Settings(..., _env_file=None)` or use the `api_module`
  fixture pattern.
- `starlette.testclient` needs the `httpx2` package; import `Response` from
  `httpx2`.
- Real Entra tenant values are pending: leave `OIDC_*` / `VITE_ENTRA_*` blank
  locally; tests use a loopback issuer and a fake sign-in.
- macOS: use `sed -i ''` (not `sed -i`).

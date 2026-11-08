# Agent Template: Work Breakdown

Tasks are ordered by dependency and intended to be completed as small, independently testable changes. This is a solo-developer repository: commit directly to `main`, without feature branches or PRs. CI runs on each push and reports failures, but cannot block a commit that has already been pushed. Defer PR templates and PR-based branch protection unless the workflow changes. Starting in Phase 2, make one descriptive commit per completed task.

The project starts as a documentation-only folder, not a Git repository. Keep development local and Azure-free until the explicit cloud gates below. Never commit secrets, local databases, Terraform state, or saved plan files. Do not mark a task done until its acceptance checks pass.

## Phase 0: Product decisions and delivery contract

- [x] Confirm repository name, GitHub owner, default branch, and initial visibility.
- [x] Confirm that the MVP is one free subscription per person and one persistent conversation per subscription; define reset, retention, and deletion expectations.
- [x] Confirm the plain-agent boundary: no custom persona/system prompt, tools, retrieval, or elaborate agent orchestration; allow only minimal provider-required configuration and document defaults.
- [x] Confirm Entra External ID as the target identity provider; record tenant and SPA/API registration values as pending until provisioned. Defer real sign-up acceptance tests until these values are configured and verified.
- [x] Confirm Azure AI Foundry as the intended provider; defer selecting a project/model deployment and region until before live integration or provisioning, after reviewing availability, quotas, data handling, and cost. Keep the interface provider-isolated until then.
- [x] Define a USD 50/month dev/staging spend ceiling separately from Free Trial credit, plus initial targets of chat response p95 ≤ 20 seconds, 5 concurrent chat requests, and 99% monthly API availability. Defer Azure provisioning until itemized costs and quotas are verified; obtain explicit approval before exceeding the ceiling.

## Phase 1: Git and GitHub from the empty folder

- [x] Initialize Git in this project folder and check in the reviewed specs as a descriptive bootstrap commit; do not include unrelated files or secrets.
- [x] Create the GitHub repository, add the remote, push the default branch, and confirm the local/remote history is consistent.
- [x] Add contribution guidance for the solo-developer workflow, task-sized commits, review expectations, test evidence, and safe pushes.
- [x] Defer PR templates and PR-based branch protection; keep the solo workflow on `main` without branches or PRs.

## Phase 2: Runnable application skeleton and CI

- [x] Agree and pin supported Python and Node versions; choose reproducible dependency/lockfile workflows and document how to update them.
- [x] Scaffold independently runnable `backend/` (FastAPI) and `frontend/` (React, TypeScript, Vite, MUI) applications in the existing repository layout.
- [x] Add `.gitignore`, `.dockerignore`, safe `.env.example` files, and configuration validation; ensure secrets and local data are excluded.
- [x] Add a minimal API liveness route and frontend shell; verify both start locally with documented commands.
- [x] Add formatting/linting, strict type checking, and unit tests for each app, with reproducible commands (and Make targets if useful).
- [x] Add the first GitHub Actions CI workflow: run backend/frontend checks and production build on PRs and pushes; use least-privilege permissions and no Azure credentials.
- [x] Add dependency and secret scanning to CI; make failure visible and do not silently suppress findings.
- [x] Keep direct pushes to `main`; CI runs on pushes and reports failures, with no PR merge gate.
- [x] Define OpenAPI as the API contract and generate/share frontend types rather than hand-maintaining duplicate schemas.

**Why here:** CI is introduced before feature work so each later task is checked automatically. It can run without cloud resources or deployment credentials.

## Phase 3: Local persistence, health, and observability foundation

- [x] Add local PostgreSQL configuration and a disposable test database/service; document startup, migration, reset, and shutdown.
- [x] Add the single `subscriptions` SQLAlchemy model and Alembic migration with unique `(identity_issuer, identity_subject)` and UTC start-time behavior.
- [x] Add `GET /api/v1/health/live` that does not call external dependencies and `GET /api/v1/health/ready` that reflects required dependency availability.
- [x] Add privacy-safe structured API logs and request/correlation IDs; ensure error responses do not leak stack traces or configuration secrets.
- [x] Add OpenTelemetry-compatible API traces and metrics as database/API behavior is implemented, with optional local OTLP collection/viewing instructions.
- [x] Add automated tests proving tokens, credentials, and unnecessary personal data are absent from current API logs and telemetry.
- [x] Keep local observability optional for the basic app run and document its resource requirements; do not add a cloud monitoring dependency.

**Why here:** Operational visibility and privacy boundaries are cheaper to establish alongside the API than retrofit after integrations and production usage.

## Phase 4: Identity and free-subscription vertical slice

- [x] Implement OIDC discovery/JWKS validation in FastAPI with issuer, audience, signature, time claims, required claims, and delegated-scope checks; test invalid-token rejection.
- [x] Implement React/MSAL sign-up, sign-in, sign-out, callback handling, and protected-route behavior with Authorization Code + PKCE and no client secret.
- [x] Build accessible registration/login/forgot-password entry points using the verified Entra External ID flows; do not implement password storage or reset in this app.
- [x] Implement `GET /api/v1/me/subscription` as an idempotent, transaction-safe provisioner; derive identity only from validated `(issuer, subject)` claims.
- [x] Ensure email is display/contact data only and cannot identify, merge, or authorize accounts.
- [x] Add tests for retry, concurrent provisioning, changed/shared email claims, and authorization boundaries.
- [x] Complete local UI/API flow tests using a safe test identity strategy; use real Entra only when the tenant and app registrations are configured.

## Phase 5: Basic chat, fake agent, then Foundry

- [x] Define a typed server-side agent interface and deterministic fake implementation so local work and tests do not require Azure.
- [x] Implement the plain-agent chat screen and authenticated API flow: no custom persona/system prompt, tools, retrieval, or advanced orchestration.
- [x] Implement atomic creation/storage of one server-owned conversation/thread reference per authenticated subscription; reject user-supplied user, subscription, agent, or provider-thread IDs.
- [x] Add bounded message size, request rate/concurrency controls, timeouts, safe error handling, and tests for success, provider failure, timeout, retry, and cancellation/disconnect behavior.
- [x] Add end-to-end local fake-agent tests, including proof a user cannot access another user's conversation.
- [x] Confirm provider/model configuration, region, data handling, quotas, and cost before enabling live Azure AI Foundry calls.
- [x] Implement the Foundry adapter against the existing agent interface using an injected, mocked provider client (no live Azure calls, credentials, or provisioning); keep provider calls server-side and ensure no prompt/message/output is captured in telemetry.

The Azure-dependent Phase 5 items (live managed-identity authorization, privacy tests against the real adapter, streaming spike, retention verification) moved to Phase 7b.

## Phase 6: Local integration, containers, and release quality

- [x] Document and verify one local workflow for frontend, API, PostgreSQL, migrations, fake agent, and optional telemetry.
- [x] Add frontend/API integration and accessibility tests for sign-up/sign-in states, protected chat, loading/errors, and recovery navigation.
- [x] Add reproducible, non-root frontend/backend container images, health checks, and graceful shutdown; test them locally.
- [x] Add container build and vulnerability scanning to CI; publish no image or deployment credentials from untrusted PRs.
- [x] Add database migration compatibility checks and document how local developers safely reset test data.
- [x] Run the complete local suite and record commands/results before starting cloud infrastructure work.
- [x] Add an opt-in local sign-in for manual development (no Azure): a loopback OIDC issuer script plus an explicitly enabled frontend sign-in, so `make backend` + `make frontend` reach the chat with the fake agent while the API still validates real tokens; excluded from production builds, documented, and tested.

## Phase 7: Terraform and Azure dev foundation (approval required)

- [x] Pin Terraform CLI/AzureRM provider versions and commit provider lock files for supported CI/developer platforms.
- [x] Add Terraform format/init/validate and security/policy checks to PR CI; do not require Azure credentials or apply resources from CI.
- [x] Design isolated per-environment infrastructure and a separately bootstrapped remote-state backend with Entra data-plane RBAC, TLS, versioning, and soft delete.
- [x] Define a minimal dev deployment with only required resources, explicit scaling/retention/region, managed identity, least privilege, and no production resources.

**Why here:** Local behavior, tests, and container builds should be stable before cloud costs begin. Terraform checks can be automated early, but a successful validation is not authorization to create resources.

## Phase 7b: Azure gate (real subscription and explicit approval required)

Everything here needs a real Azure subscription, credentials, or provisioned resources. Do not start any item without explicit user approval.

- [x] Check subscription restrictions, current credit/spend limits, model/database region availability, quotas, data processing, and itemized expected monthly cost.
- [x] Generate and review an environment-specific plan, including all creates/updates/deletes and sensitive-resource handling; obtain explicit approval before applying.
- [x] Provision the remote-state backend only after approval and verify access/locking; provision dev only after a separately reviewed plan and explicit apply approval.
- [x] Verify TLS, identity/RBAC, network exposure, secret handling, and cost alerts for the Phase A resources (storage state backend, Foundry, budget); evidence in `infra/terraform/README.md`.
- [ ] After Phase B is deployed, verify app ingress TLS, the API's managed identity/RBAC, health probes, and privacy-safe API telemetry in dev.
- [x] Enable live Foundry calls with managed-identity authorization and verify them against the provisioned project.
- [x] Add automated tests proving chat content, prompts, model output, tokens, credentials, and unnecessary personal data are absent from logs and telemetry, including with the real adapter.
- [x] Decide streaming only after a focused spike verifies reliable cancellation, disconnect cleanup, and testability; ship a tested non-streaming response first if needed.
- [x] Document conversation retention/deletion behavior and verify the provider's actual capabilities before production.
- [x] Implement account deletion as `spec.md` requires: an authenticated endpoint that deletes the caller's own Foundry conversation (treat 404 as already deleted) and then their subscription, with tests for success, provider failure, retry after partial failure, and that one user cannot delete another's data; document it.
- [x] Verify the migrations and the API against the Supabase PostgreSQL (ADR 0005) using the ignored `backend/.env.supabase`: apply migrations, exercise subscription provisioning and account deletion end to end with the fake agent, and document the connection settings (TLS, connection mode) without exposing credentials.
- [x] Write and review the Phase B Terraform for `dev` (ADRs 0002, 0005, 0009): Log Analytics and Application Insights with a low daily cap, a Container Apps environment on the Consumption plan, one user-assigned identity, and the `api` and `web` Container Apps (scale to zero, images from GitHub Container Registry, database URL and registry token as Container Apps secrets supplied outside git); generate an itemized plan and monthly cost estimate, and stop before apply.
- [x] Apply the reviewed Phase B plan after explicit user approval, then verify it in Azure with read-only checks.

## Phase 8: Azure CI/CD and dev deployment

- [ ] Configure GitHub-to-Azure OIDC federation with an environment-scoped, least-privilege identity; no long-lived Azure credentials.
- [ ] Keep Terraform plan jobs read-only; expose only a restricted/redacted summary and never publish state or sensitive plan binaries.
- [ ] Gate applies and deployments with GitHub Environment approvals and protected branches.
- [x] Build and scan immutable frontend/backend images, reference them by commit SHA/digest, and promote the same artifacts.
- [ ] Apply database migrations via a separately controlled one-shot job with minimum permissions.
- [ ] Deploy to dev and run smoke tests for liveness/readiness, sign-up/auth, subscription provisioning, and chat; require successful checks before promotion.
- [ ] Export OpenTelemetry signals to Azure Monitor/Application Insights with access controls and retention; configure actionable alerts and verify alert delivery.
- [ ] Document app rollback, migration compatibility/recovery, deployment provenance, and incident troubleshooting.

## Phase 9: Production readiness and release (separate approval)

- [ ] Agree production SLOs, supported concurrency, rate/usage limits, privacy notice/terms, data retention/deletion, and support/incident ownership.
- [ ] Establish separate production Terraform state, resource isolation, deployment identity, GitHub Environment, approvals, and budget controls.
- [ ] Complete security, privacy, dependency, infrastructure, and AI provider reviews; verify no secrets or chat content enter source control or telemetry.
- [ ] Exercise Entra account lifecycle and Foundry conversation retention/deletion behavior end-to-end.
- [ ] Verify backup/restore and database recovery; rehearse application rollback and migration recovery.
- [ ] Run staging load tests against agreed SLOs and validate model quota, latency, and cost limits.
- [ ] Verify production dashboard, alert routing, runbooks, escalation path, and post-deployment smoke tests.
- [ ] Review the final production cost estimate and obtain explicit production provisioning/release approval.
- [ ] Deploy production via the approved pipeline and verify authentication, subscription provisioning, chat, telemetry, and rollback readiness.

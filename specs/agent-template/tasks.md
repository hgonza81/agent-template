# Agent Template: Work Breakdown

Tasks are ordered by dependency and intended to be completed as small, independently testable changes. Make one descriptive commit per completed task. Open a PR for each independently reviewable change; combine closely related task commits when they form one coherent review, rather than creating a PR for every tiny checkbox. Merge only with review and required CI checks passing.

The project starts as a documentation-only folder, not a Git repository. Keep development local and Azure-free until the explicit cloud gates below. Never commit secrets, local databases, Terraform state, or saved plan files. Do not mark a task done until its acceptance checks pass.

## Phase 0: Product decisions and delivery contract

- [ ] Confirm repository name, GitHub owner, default branch, and initial visibility.
- [ ] Confirm that the MVP is one free subscription per person and one persistent conversation per subscription; define reset, retention, and deletion expectations.
- [ ] Confirm the plain-agent boundary: no custom persona/system prompt, tools, retrieval, or elaborate agent orchestration; allow only minimal provider-required configuration and document defaults.
- [ ] Confirm the target identity provider setup: Entra External ID tenant, SPA/API registrations, redirect/logout URLs, user-flow IDs, API audience, and delegated scope. Defer real sign-up acceptance tests until these values exist.
- [ ] Confirm target Foundry project/model deployment and region before any live provider integration or provisioning; keep the interface provider-isolated until then.
- [ ] Define a monthly spend ceiling separately from Free Trial credit, plus initial latency, concurrency, and availability targets. Defer Azure provisioning until current costs and quotas are verified.

## Phase 1: Git and GitHub from the empty folder

- [ ] Initialize Git in this project folder and check in the reviewed specs as a descriptive bootstrap commit; do not include unrelated files or secrets.
- [ ] Create the GitHub repository, add the remote, push the default branch, and confirm the local/remote history is consistent.
- [ ] Add contribution guidance with task-sized commits, branch/PR workflow, review expectations, test evidence, and no direct pushes to the protected default branch.
- [ ] Add a PR template and issue/task references so each change explains intent, scope, verification, and any operational impact.
- [ ] Configure branch protection/rulesets and required CI checks once the CI workflow exists; require review and prevent force pushes to the default branch.

## Phase 2: Runnable application skeleton and CI

- [ ] Agree and pin supported Python and Node versions; choose reproducible dependency/lockfile workflows and document how to update them.
- [ ] Scaffold independently runnable `backend/` (FastAPI) and `frontend/` (React, TypeScript, Vite, MUI) applications in the existing repository layout.
- [ ] Add `.gitignore`, `.dockerignore`, safe `.env.example` files, and configuration validation; ensure secrets and local data are excluded.
- [ ] Add a minimal API liveness route and frontend shell; verify both start locally with documented commands.
- [ ] Add formatting/linting, strict type checking, and unit tests for each app, with reproducible commands (and Make targets if useful).
- [ ] Add the first GitHub Actions CI workflow: run backend/frontend checks and production build on PRs and pushes; use least-privilege permissions and no Azure credentials.
- [ ] Add dependency and secret scanning to CI; make failure visible and do not silently suppress findings.
- [ ] Configure branch protection to require the passing CI checks; verify a deliberately failing check blocks merge.
- [ ] Define OpenAPI as the API contract and generate/share frontend types rather than hand-maintaining duplicate schemas.

**Why here:** CI is introduced before feature work so each later task is checked automatically. It can run without cloud resources or deployment credentials.

## Phase 3: Local persistence, health, and observability foundation

- [ ] Add local PostgreSQL configuration and a disposable test database/service; document startup, migration, reset, and shutdown.
- [ ] Add the single `subscriptions` SQLAlchemy model and Alembic migration with unique `(identity_issuer, identity_subject)` and UTC start-time behavior.
- [ ] Add `GET /api/v1/health/live` that does not call external dependencies and `GET /api/v1/health/ready` that reflects required dependency availability.
- [ ] Add privacy-safe structured API logs and request/correlation IDs; ensure error responses do not leak stack traces or configuration secrets.
- [ ] Add OpenTelemetry-compatible API traces and metrics as database/API behavior is implemented, with optional local OTLP collection/viewing instructions.
- [ ] Add automated tests proving tokens, credentials, and unnecessary personal data are absent from logs and telemetry; add chat-content assertions with the chat slice.
- [ ] Keep local observability optional for the basic app run and document its resource requirements; do not add a cloud monitoring dependency.

**Why here:** Operational visibility and privacy boundaries are cheaper to establish alongside the API than retrofit after integrations and production usage.

## Phase 4: Identity and free-subscription vertical slice

- [ ] Implement OIDC discovery/JWKS validation in FastAPI with issuer, audience, signature, time claims, required claims, and delegated-scope checks; test invalid-token rejection.
- [ ] Implement React/MSAL sign-up, sign-in, sign-out, callback handling, and protected-route behavior with Authorization Code + PKCE and no client secret.
- [ ] Build accessible registration/login/forgot-password entry points using the verified Entra External ID flows; do not implement password storage or reset in this app.
- [ ] Implement `GET /api/v1/me/subscription` as an idempotent, transaction-safe provisioner; derive identity only from validated `(issuer, subject)` claims.
- [ ] Ensure email is display/contact data only and cannot identify, merge, or authorize accounts.
- [ ] Add tests for retry, concurrent provisioning, changed/shared email claims, and authorization boundaries.
- [ ] Complete local UI/API flow tests using a safe test identity strategy; use real Entra only when the tenant and app registrations are configured.

## Phase 5: Basic chat, fake agent, then Foundry

- [ ] Define a typed server-side agent interface and deterministic fake implementation so local work and tests do not require Azure.
- [ ] Implement the plain-agent chat screen and authenticated API flow: no custom persona/system prompt, tools, retrieval, or advanced orchestration.
- [ ] Implement atomic creation/storage of one server-owned conversation/thread reference per authenticated subscription; reject user-supplied user, subscription, agent, or provider-thread IDs.
- [ ] Add bounded message size, request rate/concurrency controls, timeouts, safe error handling, and tests for success, provider failure, timeout, retry, and cancellation/disconnect behavior.
- [ ] Add end-to-end local fake-agent tests, including proof a user cannot access another user's conversation.
- [ ] Confirm provider/model configuration, region, data handling, quotas, and cost before enabling live Azure AI Foundry calls.
- [ ] Implement the Foundry adapter and managed-identity authorization; keep provider calls server-side and ensure no prompt/message/output is captured in telemetry.
- [ ] Add automated tests proving chat content, prompts, model output, tokens, credentials, and unnecessary personal data are absent from logs and telemetry.
- [ ] Decide streaming only after a focused spike verifies reliable cancellation, disconnect cleanup, and testability; ship a tested non-streaming response first if needed.
- [ ] Document conversation retention/deletion behavior and verify the provider's actual capabilities before production.

## Phase 6: Local integration, containers, and release quality

- [ ] Document and verify one local workflow for frontend, API, PostgreSQL, migrations, fake agent, and optional telemetry.
- [ ] Add frontend/API integration and accessibility tests for sign-up/sign-in states, protected chat, loading/errors, and recovery navigation.
- [ ] Add reproducible, non-root frontend/backend container images, health checks, and graceful shutdown; test them locally.
- [ ] Add container build and vulnerability scanning to CI; publish no image or deployment credentials from untrusted PRs.
- [ ] Add database migration compatibility checks and document how local developers safely reset test data.
- [ ] Run the complete local suite and record commands/results before starting cloud infrastructure work.

## Phase 7: Terraform and Azure dev foundation (approval required)

- [ ] Pin Terraform CLI/AzureRM provider versions and commit provider lock files for supported CI/developer platforms.
- [ ] Add Terraform format/init/validate and security/policy checks to PR CI; do not require Azure credentials or apply resources from CI.
- [ ] Design isolated per-environment infrastructure and a separately bootstrapped remote-state backend with Entra data-plane RBAC, TLS, versioning, and soft delete.
- [ ] Define a minimal dev deployment with only required resources, explicit scaling/retention/region, managed identity, least privilege, and no production resources.
- [ ] Check subscription restrictions, current credit/spend limits, model/database region availability, quotas, data processing, and itemized expected monthly cost.
- [ ] Generate and review an environment-specific plan, including all creates/updates/deletes and sensitive-resource handling; obtain explicit approval before applying.
- [ ] Provision the remote-state backend only after approval and verify access/locking; provision dev only after a separately reviewed plan and explicit apply approval.
- [ ] Verify TLS, identity/RBAC, network exposure, secret handling, health probes, cost alerts, and privacy-safe telemetry in dev.

**Why here:** Local behavior, tests, and container builds should be stable before cloud costs begin. Terraform checks can be automated early, but a successful validation is not authorization to create resources.

## Phase 8: Azure CI/CD and dev deployment

- [ ] Configure GitHub-to-Azure OIDC federation with an environment-scoped, least-privilege identity; no long-lived Azure credentials.
- [ ] Keep Terraform plan jobs read-only; expose only a restricted/redacted summary and never publish state or sensitive plan binaries.
- [ ] Gate applies and deployments with GitHub Environment approvals and protected branches.
- [ ] Build and scan immutable frontend/backend images, reference them by commit SHA/digest, and promote the same artifacts.
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

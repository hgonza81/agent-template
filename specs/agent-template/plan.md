# Agent Template: Implementation Plan

## Delivery approach: build from an empty folder

This workspace currently contains specifications, not an initialized Git repository or application. Start by making the work reviewable, then deliver local, testable slices before introducing Azure:

1. Agree the repository name/owner and a few product decisions that would otherwise change architecture. Keep undecided provider configuration behind an adapter.
2. Initialize Git, make the first documentation/bootstrap commit, create the GitHub repository, push the default branch, and establish branch protection and PR conventions.
3. Scaffold the smallest runnable frontend and FastAPI backend, local database/dev setup, and automated CI. CI belongs here—not near deployment—so every later task gets fast feedback.
4. Implement the health, persistence, authentication, and chat slices locally. Use a deterministic fake agent until the real Foundry integration is approved and configured.
5. Add privacy-safe logs and request correlation with the first API slice; introduce traces, metrics, and local telemetry viewing before the app grows. Move the same OpenTelemetry signals to Azure Monitor when Azure exists.
6. Containerize and verify the whole app locally. Add infrastructure validation to CI before provisioning anything.
7. Provision a single Azure dev environment only after region, identity, data-retention, and cost reviews. Add Azure deployment automation only after that foundation works.
8. Treat production as a separately approved release milestone, not an automatic consequence of a successful dev deployment.

### Git, commits, and pull requests

- Make one descriptive commit per completed task (or indivisible implementation unit), with tests and documentation included. Do not mark a task done until its checks pass.
- Push task commits on a feature branch and open a PR for each independently reviewable change. Combine tightly coupled task commits into one PR when splitting them would make review or testing misleading; avoid a PR for every tiny checkbox.
- Keep PRs small, explain the intent and trade-offs, link the task, include test results, and use CI-required status checks. Merge only after review and green checks.
- Use a protected default branch and prohibit direct pushes once configured. Keep secrets, local databases, Terraform state, and plan files out of Git.
- For the initial repository bootstrap, the first commit can be made locally before the GitHub remote exists; push it and open a PR for subsequent work once the remote and default branch are established.

### When CI/CD belongs

- **CI starts with the app skeleton.** On each PR, run formatting/linting, type checks, unit tests, backend tests (with disposable PostgreSQL where needed), frontend production build, and secret/dependency checks. Add container and Terraform validation as those assets are introduced. CI must not need Azure credentials or provision resources.
- **CD comes later.** First build reproducible containers and deploy manually or through a controlled dev workflow after the Azure dev foundation is approved. Then configure GitHub Actions OIDC, environment-scoped permissions, approvals, immutable image promotion, migrations, smoke tests, and rollback. Never put long-lived Azure credentials in GitHub secrets.
- **Production CD is a further gate.** Use separate production state, identity, environment approvals, reviewed cost estimates, backup/restore evidence, SLOs, alert delivery, and a rollback plan.

### When observability belongs

- Add structured, privacy-safe logs, request/correlation IDs, and independent liveness/readiness behavior with the first API skeleton; retrofitting these later makes debugging and operational boundaries harder.
- Add OpenTelemetry-compatible traces and metrics as database/auth/chat dependencies arrive. Develop and inspect telemetry locally (for example via a local OTLP collector and a lightweight local viewer); keep this optional for the basic app run and document its resource cost.
- Instrument the browser/API boundary for request duration and failures, but do not capture message text, prompts, model output, tokens, credentials, or unnecessary personal data. Add tests that enforce these exclusions.
- Once Azure is approved, export the same signals to Azure Monitor/Application Insights and add actionable alerts, retention/access controls, dashboards, and an operational runbook. Do not deploy a costly monitoring stack to Azure just to claim observability.

## Spec-driven development workflow

Treat [`spec.md`](./spec.md) as the product contract and [`tasks.md`](./tasks.md) as the ordered implementation checklist. For each vertical slice:

1. Resolve the relevant open product/security decision and update the specification.
2. Convert acceptance criteria into tests before or alongside implementation.
3. Implement the smallest end-to-end slice across UI, API, persistence, and provider integration.
4. Run focused tests, lint/type checks, and security checks; record exact commands and results.
5. Update the task status only after its acceptance checks pass and the change is reviewed.
6. Never provision or apply Terraform merely to make a task appear complete; cloud changes require a reviewed plan, cost review, and explicit approval.

## Proposed architecture

```text
Browser
  React + TypeScript + Material UI
  MSAL browser auth (Authorization Code + PKCE)
       |
       | HTTPS + Entra External ID access token
       v
FastAPI API (JWT validation, subscription provisioning, chat orchestration)
       |                  |                       |
       |                  | managed identity      | managed identity
       v                  v                       v
PostgreSQL           Azure AI Foundry         Azure Key Vault
(local first;        Agent Service            only if secrets are required
Azure in dev/prod)
       |
       +-- subscriptions table:
           identity issuer + subject, email snapshot, start time,
           and server-managed Foundry thread ID

OpenTelemetry
  local development: structured logs, traces, metrics, local OTLP tooling
  Azure environments: Azure Monitor / Log Analytics / Application Insights

GitHub Actions --> CI from the first runnable app; CD after dev approval
Terraform --> isolated Azure resource group and environment
GitHub Actions -- OIDC federation --> Azure deployment identity (later)
```

## Technology choices

- **Frontend:** React, TypeScript, Vite, Material UI, and the Entra-supported MSAL React/browser libraries.
- **Authentication and password recovery:** Microsoft Entra External ID customer identity. Entra owns password lifecycle, email verification, sign-in, sign-out, and forgot/reset-password flow. The SPA uses Authorization Code with PKCE; the API independently validates bearer tokens.
- **API:** FastAPI with typed request/response models, Pydantic settings, and generated OpenAPI.
- **Persistence:** PostgreSQL through SQLAlchemy 2.x and Alembic. One application-owned table, `subscriptions`; no tenant, client, password, or chat-message tables.
- **Identity mapping:** Unique `(issuer, subject)` pair from the validated token. Email is a non-authoritative snapshot only.
- **Agent:** Keep Azure AI Foundry Agent Service as the intended hosted provider, accessed server-side by FastAPI using managed identity. Keep a typed provider boundary and deterministic fake for local development/tests. No project, model deployment, or region is selected yet; choose them immediately before live integration or provisioning, after reviewing availability, quotas, data handling, and cost. The initial product agent is deliberately plain: no app-authored persona or custom instructions/system prompt, tools, knowledge base, or application-managed guardrails. Provider/model defaults and mandatory platform safety behavior still apply; do not promise a behavior-free model.
- **Conversation storage:** Foundry Agent Service owns thread/message history. The `foundry_thread_id` stored on the subscription binds the one MVP thread to its owner. Retention/deletion must be confirmed before production.
- **Hosting:** Azure Container Apps for the web frontend and API. Deploy separately so the API can remain private or restricted if the selected topology permits; only the browser-facing app should be public by default.
- **Registry:** Azure Container Registry with immutable commit-SHA or digest references and admin credentials disabled where supported.
- **Secrets and identity:** Managed identity for supported Azure data-plane access; Azure Key Vault for unavoidable secrets. No long-lived Azure credentials in GitHub.
- **Observability:** OpenTelemetry instrumentation and privacy-safe structured logs from the first API slice; local OTLP collection/viewing for development; Azure Monitor/Log Analytics and Application Insights after Azure approval. No self-hosted Grafana/ELK production stack.
- **Infrastructure as code:** Terraform with pinned CLI/provider versions, committed provider lock file, reusable modules, isolated environment state, and an Azure Storage backend protected by Entra data-plane RBAC.
- **CI/CD:** GitHub Actions for frontend/API quality, tests, container builds/scans, Terraform validation/plans, and later deployment through OIDC. Applies remain protected by GitHub Environment approval.

## Registration and subscription provisioning

Entra External ID user-flow registration is not itself a transaction with the application database. Do not assume a synchronous identity-provider webhook. After the SPA returns from successful sign-up with an access token, it calls `GET /api/v1/me/subscription` (or an equivalent idempotent provisioning operation). FastAPI validates the token and inserts the free subscription using the unique issuer/subject constraint. A transaction conflict resolves concurrent first requests by returning the existing row. The UI enters the chat after provisioning succeeds.

The operation does not accept a user ID, email, subscription type, Foundry thread ID, or tenant ID from the request body. The API derives identity from verified claims and creates the only supported free subscription in code.

## Authentication design

- Entra External ID is selected, but the tenant and SPA/API app registrations are not provisioned. Keep tenant/issuer, client IDs, redirect/logout URIs, user-flow IDs, API audience, and delegated scope as TBD; defer real sign-up acceptance tests until configured and verified.
- Configure Entra External ID customer tenant and separate SPA/API app registrations with the API audience and least-privilege delegated scope.
- Configure self-service email/password sign-up and password reset; verify the exact provider-supported flow before promising behavior.
- Configure only approved frontend redirect/logout URLs and use PKCE. The SPA has no client secret.
- FastAPI uses OIDC discovery and cached JWKS with key-rotation support; verify RS256/signature, issuer, audience, `exp`, `nbf`, required claims, and the required scope.
- Treat `(iss, sub)` as the internal stable account key. Never authorize by email.
- Keep auth state and errors consistent across protected React routes; clear local state and use the provider sign-out endpoint on logout.

## Chat design

- The browser sends the user's text only to FastAPI over HTTPS.
- FastAPI authenticates and resolves the caller's subscription before contacting Foundry.
- On first chat request, create the Foundry thread server-side, persist its identifier on the caller's subscription, and handle concurrent thread creation atomically.
- Send user text to the configured Foundry agent/model. Do not accept arbitrary project, agent, deployment, system prompt, or thread IDs from the caller.
- Return a bounded response, preferably streamed with Server-Sent Events if the Foundry SDK/API supports reliable cancellation and disconnect cleanup. Otherwise use a normal response for the first slice and add streaming after a focused spike.
- Apply message-size, rate, timeout, retry, and per-user/model usage controls. Avoid blind retries for non-idempotent message creation.
- Never log message bodies, raw prompts, model output, tokens, or provider credentials. Use request IDs and non-sensitive operation/duration/error metadata.
- Test that untrusted chat content or model output cannot alter application authorization or invoke unapproved capabilities. This is a boundary test, not a custom prompt/guardrail framework.

## Azure resource shape

Provision only after checking subscription restrictions, region/model availability, costs, and approvals:

- One new project resource group per environment.
- Azure Container Apps for React static serving and the FastAPI API; choose ingress, scaling, and network isolation based on the cost/security review.
- Azure Container Registry for immutable frontend/API images.
- Azure Database for PostgreSQL Flexible Server for the subscription record.
- Azure AI Foundry project/Agent Service and the approved model deployment; verify supported managed identity/RBAC and regional data-processing behavior.
- User-assigned managed identity for the API, with scoped permissions for Foundry and Key Vault.
- Key Vault only for secrets that cannot use managed identity or secret references.
- Azure Monitor/Log Analytics/Application Insights and low-cost actionable alerts; exclude prompt/response data.
- Terraform state in a separate secured Azure Storage account/container with blob versioning, soft delete, and environment-scoped Entra roles.

Avoid adding API Management, Front Door, a self-hosted identity system, Grafana, or ELK to the MVP unless requirements or measured load justify their additional cost and maintenance.

## Repository layout

```text
frontend/                 React + TypeScript + MUI SPA
backend/                  FastAPI application
  src/<package>/api/      versioned routes and auth
  src/<package>/          settings, models, persistence, Foundry adapter
  migrations/             Alembic migrations
  tests/                  unit, API, and integration tests
infra/terraform/          root environments, modules, backend bootstrap
specs/agent-template/    spec.md, plan.md, tasks.md
.github/workflows/        frontend/backend/infra CI and deployment
```

Keep the frontend and backend independently buildable and testable. Share only the generated OpenAPI contract or a generated typed client; do not duplicate API schemas manually.

## Quality and release strategy

- Frontend: formatting/linting, strict TypeScript, component/auth-flow tests, accessibility checks, production build, and dependency audit.
- Backend: Ruff, strict type checking, pytest, coverage, OpenAPI checks, dependency audit, and database integration tests against disposable PostgreSQL.
- Provider tests: inject a Foundry interface and use a fake deterministic implementation for unit/integration tests; live Foundry checks are opt-in and run only with approved test credentials.
- Containers: reproducible dependency locks, non-root runtime, health check, graceful shutdown, image vulnerability scan, and immutable tags.
- Infrastructure: Terraform fmt/init/validate and security/policy checks on PRs. Publish redacted/restricted plan summaries; never upload state or saved plan binaries as public artifacts.
- CI runs from the first runnable skeleton and stays independent of Azure credentials. Add checks in the same commit/PR as each new concern (containers, IaC, migrations, telemetry).
- Local release: run the frontend, API, PostgreSQL, fake agent, and optional local telemetry tooling from documented commands; verify end-to-end flows and production builds before cloud work.
- Deployment: after dev provisioning approval, build once and deploy the same immutable image to dev, run smoke/auth/chat checks, then promote by approval. Production release remains blocked until SLOs, cost, privacy, backup/recovery, and support are approved.

## Cost and security gates

- A USD 200 Free Trial credit is a balance, not a monthly spending target or hard spending cap.
- The approved initial dev/staging ceiling is USD 50 per month, separate from trial credit. Do not provision if the itemized expected monthly cost exceeds it without explicit approval of a revised ceiling.
- Before applying: check the credit remaining, subscription spending limit, Azure service and model regional availability, fixed monthly resources, Foundry token/model costs, telemetry ingestion, networking, database/storage, and taxes.
- Configure budgets/alerts where supported, while documenting that alerts may lag and do not guarantee a hard cap.
- Begin with one dev environment, scale-to-zero where appropriate, low-cost database sizing only if available, bounded Foundry quotas, and log retention sized to need.
- Do not provision staging or production until dev behavior, data retention, and monthly cost are reviewed.
- Initial dev/staging targets: complete chat response p95 ≤ 20 seconds, at least 5 concurrent chat requests, and 99% monthly API availability measured by readiness probes. Validate these targets against actual service quotas and costs; they are not production SLOs.

## Open decisions to resolve before the affected tasks

1. Provision and configure the Entra External ID tenant and SPA/API registrations before real sign-up tests.
2. Select the Foundry project/model deployment and region before live integration or provisioning, after checking data handling, regional availability, quotas, and costs.
3. Verify the selected region supports the chosen model and database under the subscription's current limits.
4. Keep the itemized dev/staging estimate within the approved USD 50 monthly ceiling; obtain explicit approval before exceeding it. Validate the initial dev/staging targets documented in [`spec.md`](./spec.md), and agree separate production SLOs before production.

The MVP conversation model and lifecycle are resolved in [`spec.md`](./spec.md): one free subscription and persistent thread per person, no reset, retention while the account is active, and subscription/thread deletion on account deletion. Verify provider-side deletion behavior before production. The dev/staging budget and initial performance/availability targets are also agreed; verify actual costs and quotas before provisioning. Resolve Entra details before real sign-up testing and Foundry/region details before live integration or provisioning.

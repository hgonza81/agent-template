# Agent Template: Feature Specification

## Status

Proposed baseline for a new repository. This specification describes intended behavior and does not indicate that the application or Azure resources have been created. The workspace starts as a documentation-only folder; Git/GitHub setup and the application itself are future tasks.

## Objective

Build a web application from an empty project folder where a person can register, receive one free subscription, sign in, reset a forgotten password, and chat with a basic AI agent hosted on Azure AI Foundry. Develop and validate as much as possible locally before paying for or provisioning Azure resources, then take the reviewed application through a staged path to production.

## Product decisions and assumptions

- Each authenticated person has exactly one subscription.
- The only subscription is free. Do not model a plan, tier, mode, price, billing account, or tenant.
- A subscription is created automatically after successful registration and is never created from user-supplied identity data.
- Microsoft Entra External ID is the system of record for credentials, email/password authentication, email verification, and password recovery. The application stores no password, password hash, or reset token.
- Entra External ID is the selected identity provider, but its tenant and SPA/API registrations are not yet provisioned. Tenant/issuer, client IDs, redirect and logout URIs, user-flow IDs, API audience, and delegated scope remain TBD; defer real sign-up acceptance tests until these values are configured and verified.
- The validated `(issuer, subject)` pair from an access token is the stable user identity. Email is a display/contact snapshot, not an identifier or authorization key.
- Each person has exactly one free subscription and one persistent chat thread. Azure AI Foundry Agent Service owns the thread and message history; the application stores the Foundry thread identifier on the subscription so access is bound to the authenticated user.
- The MVP does not support resetting or replacing the conversation. Retain the thread while the account is active; on a user-requested account deletion, delete the subscription and its Foundry thread. Verify and test the provider's deletion semantics before production; if provider-side deletion is unavailable or delayed, agree and disclose the actual behavior before launch.
- Azure AI Foundry is the intended hosted agent provider, but no project, model deployment, or region is selected or provisioned yet. Choose them immediately before live integration or provisioning, after reviewing availability, quotas, data handling, and cost; until then, keep the provider interface isolated and use the deterministic local fake. The MVP agent is intentionally simple: no custom persona/system prompt, tools, retrieval/knowledge base, or application-managed guardrail framework. Only minimal provider-required configuration is allowed; provider/model defaults and mandatory platform safety behavior still apply.
- The initial deployment is a single development environment. A USD 200 Free Trial credit is not treated as a monthly budget; resource and usage estimates must be reviewed before provisioning.
- The initial dev/staging spending ceiling is USD 50 per month, separate from Free Trial credit. Do not provision if the itemized expected monthly cost exceeds this ceiling without explicit approval of a revised ceiling; budgets and alerts are not hard spending caps.
- Initial dev/staging targets are complete chat response p95 at or below 20 seconds, at least 5 concurrent chat requests, and 99% monthly API availability measured by readiness probes. These are validation targets, not production SLOs.
- Azure resources for the new project are isolated in its own resource group, Terraform state, identity configuration, and container registry. Do not import or modify resources from another project.
- CI is established as soon as the application skeleton exists and does not require Azure credentials. Azure CD follows only after the dev environment, costs, and deployment identity have been reviewed.
- Git commits are task-sized and descriptive. Each completed task is committed separately and pushed directly to `main`; this solo-developer workflow does not use feature branches or PRs. CI runs on pushes and reports failures, but does not block commits already pushed to `main`.

## Users and core flows

### Registration

1. A visitor opens the React registration page.
2. The browser redirects to the configured Entra External ID email/password sign-up flow.
3. Entra performs the provider-required email verification and creates the identity.
4. The browser receives an access token using Authorization Code with PKCE and calls the authenticated API.
5. The API validates the token and idempotently creates the user's free subscription if it does not already exist.
6. The user lands in the protected chat experience.

Registration and subscription creation must be safe to retry. Concurrent first requests for the same identity must still create exactly one subscription.

### Sign-in and sign-out

- The user can sign in through Entra External ID and return to the application.
- Protected routes and APIs reject missing, invalid, expired, wrong-issuer, wrong-audience, or insufficient-scope tokens.
- Sign-out clears the local session and uses the identity provider's supported sign-out flow.
- Tokens are not written to application logs or exposed to the API's error responses.

### Forgot and reset password

- The UI provides a **Forgot password?** path from sign-in.
- Entra External ID owns the reset flow, verification, and credential change. The application never asks for or handles a user's existing password.
- On successful reset, the user can sign in with the new password.
- Do not reveal whether an email address is registered in application-owned responses.

### Chat

- An authenticated user can send a message and receive a response from the configured Azure AI Foundry agent.
- The API derives the subscription from the validated identity; callers cannot select a subscription, user, tenant, agent, or Foundry thread belonging to someone else.
- The user's Foundry thread ID is created on first chat use and stored on that user's subscription row. Thread lookups and updates are always scoped by subscription.
- The first release has one ongoing thread per subscription; resetting, clearing, or starting another conversation is out of scope unless explicitly approved.
- Retain the thread while the account is active. Account deletion removes the subscription and its associated Foundry thread; verify and test provider-side deletion behavior before production.
- The frontend supports an in-progress state, retryable failures, and cancellation where supported by the Foundry API.
- Chat text is not included in application, Azure Monitor, or security logs.
- Model and agent identifiers are deployment configuration, never accepted from an unauthenticated or arbitrary client request.
- The MVP presents a plain conversational agent and does not add a custom prompt/persona, tools, retrieval, or elaborate agent orchestration. Do not claim that provider-level defaults or required safety controls are absent.

## Local-first development and observability

- The frontend, FastAPI API, PostgreSQL, and deterministic fake-agent path can be run and tested locally using documented commands, without Azure credentials or live AI calls.
- The initial API slice includes structured logs, request/correlation IDs, and independent liveness/readiness endpoints. Add traces and metrics as database, identity, and chat dependencies are introduced.
- Use OpenTelemetry-compatible instrumentation so local signals can later be exported to Azure Monitor. Local telemetry viewing is optional for the basic run and must not require a paid cloud service.
- Telemetry is limited to operational metadata (for example request duration, status, dependency name, and safe error category). Never record user message text, prompts, model output, tokens, credentials, or unnecessary personal data in logs, traces, or metrics.
- CI runs on every PR from the first runnable skeleton and checks the relevant frontend/backend tests, formatting/linting, type checks, builds, and later container/IaC checks. CI does not provision infrastructure.
- Azure observability, alerts, and deployment automation are enabled only after the Azure dev foundation is explicitly approved. Production requires separate operational and cost approval.

## Data model

The application database has one application-owned table: `subscriptions`.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | Generated by the application; primary key |
| `identity_issuer` | String | Required; exact validated token issuer |
| `identity_subject` | String | Required; stable validated subject claim |
| `email_snapshot` | String, nullable | Optional normalized display/contact snapshot; never used as identity |
| `started_at` | UTC timestamp | Required; generated by the database/application at creation |
| `foundry_thread_id` | String, nullable | Server-managed Azure AI Foundry thread identifier; never accepted from a request body |

Constraints and rules:

- Add a unique constraint on `(identity_issuer, identity_subject)` to make subscription provisioning idempotent.
- Do not add a `tenant_id`, subscription type/plan, price, billing status, password, password hash, or reset token.
- `email_snapshot` may be refreshed from a validated token only according to a documented policy; an email change must not create another subscription.
- Do not store chat messages in PostgreSQL for the MVP. Azure AI Foundry Agent Service owns the thread history. Retain it while the account is active; account deletion removes the subscription and its associated Foundry thread. Verify and test provider-side deletion behavior before production, and disclose any provider limitations before launch.
- The Foundry thread ID is a sensitive server-side reference; never expose it as an authorization credential.

## API requirements

Use the versioned base path `/api/v1`.

| Operation | Endpoint | Expected behavior |
|---|---|---|
| Current subscription | `GET /me/subscription` | Authenticate, idempotently provision a free subscription if absent, and return the caller's subscription representation |
| Readiness | `GET /health/ready` | Report ready only when required application dependencies can accept requests |
| Liveness | `GET /health/live` | Report process liveness without calling Azure AI Foundry or the database |
| Send chat message | `POST /chat/messages` | Authenticate, find/create the caller's Foundry thread, send a message, and return or stream the assistant response |

Additional API behavior:

- Identity and email fields are derived from validated claims, not request payloads.
- Chat requests and responses are validated, bounded, and protected by a configured maximum message length.
- Responses and errors never reveal credentials, tokens, database URLs, Azure resource identifiers that are not public API data, or stack traces.
- Use request/correlation IDs. Exclude query strings, message bodies, tokens, and personal data from logs.
- Document status codes, security schemes, request limits, and error shapes in OpenAPI.

## Frontend requirements

- React with TypeScript and Material UI (MUI).
- Provide registration, sign-in, forgot/reset-password entry points, sign-out, and a protected chat screen.
- Use the supported Entra browser authentication library and Authorization Code with PKCE; no browser client secret.
- Keep authentication state in the supported MSAL/browser mechanism; do not persist access tokens in application-managed local storage.
- Display the signed-in user's email only as profile information, not as the ownership key.
- Provide accessible labels, keyboard navigation, loading/error/empty states, responsive layout, and clear recovery navigation.
- Route unauthenticated visitors to sign-in and return them safely to the intended protected route.

## Functional acceptance criteria

1. A person can register through the Entra External ID email/password flow and obtain an access token for this API.
2. A successful first authenticated subscription request creates exactly one free subscription.
3. Repeated and concurrent subscription requests for the same `(issuer, subject)` return the same subscription without duplicates.
4. Different external identities receive separate subscriptions even if they share a mutable email claim; email is never the ownership key.
5. Missing or invalid tokens cannot read subscriptions or use the chat API.
6. A user cannot read, overwrite, or use another user's subscription or Foundry thread by submitting identifiers.
7. Forgot/reset password is handled by the configured Entra flow; no password or reset token is stored by this application.
8. A user can send a chat message and receive a Foundry response through the API.
9. The Foundry conversation ID is stored server-side and is never trusted from a caller.
10. Application logs contain neither chat content nor tokens, passwords, reset tokens, or database credentials.
11. Liveness remains healthy during dependency outages; readiness reports unavailable when a required dependency is unavailable.
12. Unit and integration tests verify behavior without a live Azure subscription; Azure AI Foundry calls are replaceable with a deterministic test adapter.
13. Terraform formatting, validation, and CI checks run without provisioning cloud resources.
14. The app skeleton has an automated CI workflow before feature development depends on it; CI runs without Azure credentials.
15. A local fake-agent flow can be exercised end-to-end, and local telemetry can be inspected without sending chat content or credentials to telemetry.
16. The initial agent has no app-defined persona, custom instructions, tools, retrieval, or elaborate orchestration; provider-required defaults are documented rather than misrepresented.
17. Production is not declared ready until separate production infrastructure/identity and approvals exist, agreed SLOs are measured, alert delivery and runbooks are verified, and backup/restore and rollback have been exercised.
18. The MVP does not reset conversations; account deletion removes the subscription and its Foundry thread, with provider-side deletion behavior verified before production.

## Production release criteria

A successful local or dev deployment is not a production release. Production release requires, at minimum:

- Separate production infrastructure state, resource isolation, deployment identity, and approval gates.
- Agreed availability/latency targets, concurrency and usage limits, and a tested staged deployment/rollback process.
- Verified alert delivery, dashboards, retention/access controls, incident ownership, and operational runbooks.
- Proven database backup/restore and recovery; documented account and conversation retention/deletion behavior.
- Security, privacy, dependency, infrastructure, and provider reviews, plus an approved itemized cost estimate.
- Post-deployment authentication, subscription, chat, and health smoke checks.

## Security, privacy, and cost

- Validate JWT signature using Entra External ID OIDC discovery/JWKS metadata, issuer, audience, expiry, not-before, required claims, and delegated scope.
- Use the stable validated `(issuer, subject)` pair for identity ownership.
- Enforce authorization in FastAPI on every protected operation; hiding UI routes is not an authorization control.
- Use managed identity for API access to Foundry, Key Vault, and other supported Azure services. Grant only the required data-plane roles at the narrowest scope.
- Store unavoidable configuration secrets in Azure Key Vault; never place them in source, frontend bundles, Terraform variables committed to Git, or logs.
- Restrict CORS to explicitly approved frontend origins. Require HTTPS for deployed ingress and TLS for database connections.
- Apply request-size/rate limits and a configurable Foundry token/usage budget before enabling public signup.
- Keep chat content out of telemetry and diagnostics. Configure access control and retention for Azure AI Foundry conversation data.
- Use OpenTelemetry-compatible instrumentation, local-only tooling during development, and Azure-native Azure Monitor, Log Analytics, and Application Insights after Azure approval. Do not deploy a self-hosted monitoring stack to production.
- Estimate database, Container Apps, Foundry model/agent usage, networking, registry, secrets, and monitoring costs before provisioning. Set cost alerts/budgets where available; alerts do not guarantee a hard spending cap.
- Keep the initial dev/staging estimate at or below the approved USD 50 monthly ceiling, separate from trial credit. Revisit and obtain explicit approval before provisioning if the itemized estimate exceeds it. Validate the initial targets of chat response p95 ≤ 20 seconds, at least 5 concurrent chat requests, and 99% monthly API availability; these are not production SLOs.

## Out of scope for the first release

- Paid subscription plans, checkout, billing, invoices, and subscription upgrades.
- Multiple tenants, organizations, teams, cross-user sharing, or administrative impersonation.
- Multiple user-managed chat threads, conversation search, export, or application-owned message persistence.
- Training/fine-tuning on user conversations.
- Advanced agent behavior (custom persona/prompting framework, tools, retrieval, multi-agent orchestration, or application-managed guardrails).
- Azure production resources or production availability/performance claims before measurable SLOs, load tests, cost, and operational readiness are approved.

## Decisions requiring confirmation before implementation/provisioning

1. Provision and configure the Entra External ID tenant, application registrations, user-flow identifiers, and API scope before real sign-up tests.
2. Select the Azure AI Foundry project/model deployment and region before live integration or provisioning, after reviewing availability, quotas, data handling, and cost.
3. Verify that the selected Azure region supports the chosen model and database under the subscription's current limits.
4. Review the itemized monthly cost against the approved USD 50 dev/staging ceiling before provisioning; obtain explicit approval for any increase. Validate the initial dev/staging performance and availability targets above; agree separate production SLOs before production.
5. Check Azure service and model availability in the chosen region and obtain a complete estimate before provisioning.

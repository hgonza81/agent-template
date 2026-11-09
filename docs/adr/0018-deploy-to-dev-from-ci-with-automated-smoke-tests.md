# 0018. Deploy to dev from CI with automated smoke tests

- Status: accepted
- Date: 2026-11-08

## Context

Images are published by digest (ADR 0011), the `dev` environment has an OIDC
identity (ADR 0012) and migrations run in a Container Apps job (ADR 0017). We
need a deployment that only promotes when basic checks pass. Sign-up and chat
need a human in Entra External ID; putting user credentials in CI is not
acceptable.

## Decision

- A `deploy` job in `ci.yml` (`needs: publish`, push to `main` only,
  `environment: dev`, `id-token: write` + `contents: read`) logs in with
  `azure/login` (pinned by SHA), updates and runs the migration job to the API
  digest and waits for `Succeeded`, then updates the API and web apps to the
  published digests.
- Automated smoke tests (curl with retries to tolerate scale from zero): API
  `/api/v1/health/live` and `/ready` = 200, web `/` and `/healthz` = 200, and
  `/api/v1/me/subscription` without a token = 401.
- Sign-up/sign-in, subscription provisioning and chat are a manual checklist
  after each deployment (root README), not automated.
- Rollback is automatic on any failure after the previous images were recorded:
  the apps are updated back to those images. Migrations are not reverted; they
  must stay backward compatible (ADR 0017).
- Runs are serialized (`concurrency: deploy-dev`, no cancellation).

## Consequences

- "Promotion" is the job itself: a failed smoke test fails the run and restores
  the previous images. The `deploy` job is not a required branch check (it only
  runs on `main`).
- Rollback by re-applying the old image creates a new revision rather than
  reactivating the old one; simpler and works in single-revision mode.
- The first run needs the migration job to exist (Terraform apply pending) and
  the `dev` environment variables set.
- Real auth, provisioning and chat regressions are only caught by the manual
  checklist.

# 0017. Run migrations in a manual Container Apps job

- Status: accepted
- Date: 2026-11-08

## Context

The schema must be migrated separately from app startup, with minimum
permissions. The API image already ships `alembic.ini` and `migrations/`, and
Alembic is a runtime dependency. The database is Supabase, reached only with
the `DATABASE_URL` secret (ADR 0005), so a migration needs no Azure access.

## Decision

- `azurerm_container_app_job.migrate` in the existing `cae-agent-template-dev`
  environment, manual trigger, 300 s timeout, 0 retries, 0.25 vCPU / 0.5 GiB,
  running `alembic -c alembic.ini upgrade head` from the API image.
- No managed identity: it holds no Azure permissions. Its only secrets are the
  GHCR read token and `database-url`. The settings model also requires
  `CORS_ALLOWED_ORIGINS`, so that one non-secret value is set; no Foundry or
  OIDC variables.
- It reuses `api_image` rather than a separate variable. Terraform ignores
  image changes on the `api`, `web` and job resources, because CI deploys
  images with `az containerapp update` / `az containerapp job update`;
  `api_image` / `web_image` only matter for the first apply or a recreation.
- Nothing starts the job automatically: an operator (or a later, approved
  deploy step) runs `az containerapp job start`.

## Consequences

- A failed migration is not retried; the execution status and logs show it.
- Migrations must stay backward compatible with the running API version,
  because the job runs before or alongside a rollout.
- Terraform no longer tracks which image the apps run; the live image is read
  from Azure.

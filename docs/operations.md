# Operations (dev)

Runbook for the dev environment (`rg-agent-template-dev`). Commands marked
"not verified" were not run; everything else was checked read-only against
Azure/GitHub on 2026-11-08. Variables used below:

```sh
RG=rg-agent-template-dev API=ca-agent-template-dev-api WEB=ca-agent-template-dev-web
JOB=caj-agent-template-dev-migrate
```

## 1. Roll back the application

Both apps run in `Single` revision mode, 0 to 2 replicas. A failed `deploy`
job already restores the previous images by itself (ADR 0018). To roll back by
hand, redeploy an earlier digest; this creates a new revision (ADR 0018). Do
not use `az containerapp revision activate`: it is not part of this pipeline
and was not verified in single mode.

1. Find the previous digest: the `publish` summary of the earlier green CI run
   (`gh run list --workflow CI --branch main`, then `gh run view <id>`), or the
   inactive revision's image:
   `az containerapp revision list -g $RG -n $API --all -o table`.
2. Redeploy it (repeat for `$WEB` if the web changed):

```sh
az containerapp update -g $RG -n $API --image ghcr.io/hgonza81/agent-template-api@sha256:<previous digest>
```

3. Verify: `az containerapp show -g $RG -n $API --query properties.template.containers[0].image -o tsv`
   shows the old digest, and the smoke checks pass:
   `GET /api/v1/health/live` = 200, `/health/ready` = 200, web `/` and
   `/healthz` = 200, `/api/v1/me/subscription` without a token = 401. Then do
   the manual sign-in/subscription/chat checklist (root README).

Also stop the next push to `main` from redeploying the bad commit: revert it
in git.

## 2. Migrations: compatibility and recovery

Rules (ADR 0017): the `deploy` job migrates first, then updates the apps, and
never reverts a migration. So every migration must work with both the running
and the new API version (expand/contract):

- Expand: add nullable columns/tables/indexes with defaults; do not rename or
  drop in the same release as the code that stops using them.
- Contract: drop or tighten (NOT NULL, rename) only in a later release, after
  no running version uses the old shape.
- Keep it reversible for local use (`tests/test_migrations.py` checks
  downgrade), but do not rely on downgrading in Azure.

If a migration fails: the job does not retry, the `deploy` job stops before
updating the apps, and the running apps keep working on the old schema.

```sh
az containerapp job execution list -g $RG -n $JOB -o table
az monitor log-analytics query -w becc8fdc-4b45-48b8-8862-9c4a4c612072 --analytics-query \
  "ContainerAppConsoleLogs_CL | where ContainerJobName_s startswith 'caj-agent-template-dev-migrate' | project TimeGenerated, Log_s | order by TimeGenerated desc | take 50"
```

Logs arrive after a few minutes. Fix forward with a new commit (a new
migration), or, after fixing a transient cause such as the database being
unreachable, retry: `az containerapp job start -g $RG -n $JOB --query name -o tsv`
(the job already points at the last image; set `--image` with
`az containerapp job update` first if needed).

Cannot be reverted automatically: applied migrations, and any data they
changed or deleted. A partially applied migration is rolled back by PostgreSQL
only if it ran in a transaction (Alembic's default for PostgreSQL). Check
`alembic_version` before retrying.

Database backups: Supabase hosts PostgreSQL (ADR 0005). Backup availability,
retention and restore on the free plan are not verified, so assume none. The
table holds subscriptions only (no chat content, ADR 0003); verification is a
Phase 9 task.

## 3. Deployment provenance

- Running digest: `az containerapp show -g $RG -n $API --query properties.template.containers[0].image -o tsv`
  (same for `$WEB`; the migration job: `az containerapp job show -g $RG -n $JOB --query "properties.template.containers[0].image" -o tsv`).
  Revisions: `az containerapp revision list -g $RG -n $API --all -o table`.
- Digest to commit: CI tags each image `ghcr.io/hgonza81/agent-template-{api,web}:<commit SHA>`
  and pushes it only from `main`; the `publish` job summary of that run lists
  the digests (ADR 0011). Search the run summaries (`gh run view <id>`) for
  the digest. Listing GHCR versions with `gh api` needs a token with
  `read:packages` (not verified here).
- Commit to run: `gh run list --workflow CI --branch main`; the run title is
  the commit subject and its `deploy` job shows what was deployed. Images only
  carry `org.opencontainers.image.source`, no revision label.

## 4. Troubleshooting

| Symptom | Check |
| --- | --- |
| First request slow or times out | Apps scale to zero; the cold start takes seconds to a minute. Retry (smoke tests retry for ~5 minutes). |
| `/health/live` fails | The container is not running: `az containerapp logs show -g $RG -n $API --type system --tail 50`, check the revision `HealthState` and provisioning state. Liveness never touches the database. |
| `/health/ready` is 503 | Database or configuration unreachable. Check the `database-url` secret (Supabase paused or password changed) and the Supabase session pooler. |
| API 401 | Expected without a token. With a token: wrong issuer/audience/scope (`OIDC_*` settings), expired token, or Entra unreachable. |
| API 503 | Provider or identity unavailable (generic response; use `request_id` to find the trace). |
| Sign-in fails in the browser | Web `VITE_ENTRA_*` values are baked in at build; compare them with the Entra app registration and redirect URIs, then rebuild if wrong. |
| Revision fails to start with an image pull error | The `ghcr-token` secret (`read:packages`) expired or was revoked. Create a new token and update the secret on `api`, `web` and the job (Terraform `ghcr_read_token`, or `az containerapp secret set`, not verified). |
| `terraform` reports a state lock | Confirm no Terraform process runs, then `terraform force-unlock <lock id>` and check Azure for half-created resources (`infra/terraform/README.md`). |
| Alert email arrives | `alert-agent-template-dev-api-5xx` (more than 5 5xx in 15 min) or `...-restarts` (more than 3 restarts): look at the queries below and the latest deploy. |

Logs and telemetry are in Log Analytics workspace `log-agent-template-dev`
(customer ID `becc8fdc-4b45-48b8-8862-9c4a4c612072`) and Application Insights
`appi-agent-template-dev`. Telemetry holds no tokens, chat text or exception
details. Safe queries (run with `az monitor log-analytics query -w <id> --analytics-query "..."`):

```kusto
AppRequests | where TimeGenerated > ago(1h) | summarize n=count() by ResultCode
AppRequests | where TimeGenerated > ago(1h) and toint(ResultCode) >= 500 | project TimeGenerated, Name, ResultCode, DurationMs
ContainerAppSystemLogs_CL | where ContainerAppName_s == 'ca-agent-template-dev-api' | project TimeGenerated, Reason_s | order by TimeGenerated desc | take 20
```

Do not paste tokens, connection strings or chat content into tickets or logs.

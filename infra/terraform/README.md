# Terraform

- Terraform CLI is pinned to `~> 1.17.0` (`.terraform-version` = 1.17.1) and
  AzureRM to `5.13.0` in `versions.tf`.
- `.terraform.lock.hcl` holds hashes for linux_amd64, linux_arm64,
  darwin_arm64, darwin_amd64, and windows_amd64. After changing a provider
  version, regenerate it with
  `terraform providers lock -platform=linux_amd64 -platform=linux_arm64 -platform=darwin_arm64 -platform=darwin_amd64 -platform=windows_amd64`.
- State and plan files are git-ignored. Nothing here may be applied without
  an approved plan.
- PR CI (`terraform` job in `.github/workflows/ci.yml`) runs `terraform fmt
  -check`, `init -backend=false -lockfile=readonly`, `validate`, and a Checkov
  security/policy scan. It needs no Azure credentials and never plans or
  applies. Run the first three locally from this directory before committing.

Operational runbook (rollback, migration recovery, provenance, incidents):
[`docs/operations.md`](../../docs/operations.md).

## Environment and state design

Phase A is provisioned (see "Provisioned (Phase A)" below); Phase B items are still design only.

Layout under `infra/terraform/`:

- `bootstrap/`: creates the remote-state backend. Applied once, by a human,
  with local state that is never committed. Separate from every environment.
- `modules/`: reusable modules shared by environments (no provider
  credentials or environment names hard-coded).
- `environments/<env>/` (`dev` first; `prod` is a later gate): one root module
  per environment, each with its own backend key, its own variables, and its
  own resource group. Environments never share state, resource groups,
  identities, or databases.

Isolation per environment:

- One new resource group per environment (`rg-agent-template-<env>`); the
  environment name is part of every resource name and tag.
- One state blob per environment (`<env>/terraform.tfstate`) in a dedicated
  container, with its own least-privilege role assignment so the dev identity
  cannot read or write prod state.

Remote-state backend (bootstrap):

- Dedicated resource group and storage account, separate from workload
  resources. Not managed by the environment roots (no self-referencing state).
- TLS only: `https_traffic_only_enabled = true`, `min_tls_version = "TLS1_2"`.
- Entra data-plane RBAC only: `shared_access_key_enabled = false`,
  `default_to_oauth_authentication = true`, backend configured with
  `use_azuread_auth = true`. Access is `Storage Blob Data Contributor`
  scoped to the specific container, granted per environment identity. No
  account keys or SAS tokens.
- Blob versioning enabled and blob/container soft delete enabled (retention
  documented in the bootstrap module, at least 14 days).
- `allow_nested_items_to_be_public = false`; public network access and
  firewall rules decided in the cost/security review (task: network exposure).
- State locking uses the native blob lease; verified after provisioning.
- Resource lock (`CanNotDelete`) on the backend account.

Open items handled by later tasks: concrete resources and region (minimal dev
deployment), subscription/quota/cost checks, plan review, and approved apply.

## Minimal dev deployment (design, not yet provisioned)

Design only; `environments/dev` holds exactly these resources in one new
resource group, `rg-agent-template-dev`. Nothing is created without the
reviewed plan and explicit apply approval, and no production resources exist
in this environment.

Region: one region for every resource, variable `location`. The original
`eastus2` proposal is superseded by the availability check below, which
recommends `centralus`.

| Resource | Explicit sizing / policy |
| --- | --- |
| Log Analytics workspace + Application Insights (workspace-based) | `PerGB2018`, retention 30 days, daily ingestion cap 0.5 GB; no prompt/response data |
| Azure Container Registry | `Basic`, admin user disabled, no geo-replication, untagged-manifest cleanup |
| Container Apps environment (Consumption) | No zone redundancy, no dedicated workload profile |
| Container App `api` | min replicas 0, max 2, 0.5 vCPU / 1 GiB, ingress restricted to the web app if the topology allows, otherwise external with JWT validation |
| Container App `web` | min replicas 0, max 2, 0.25 vCPU / 0.5 GiB, the only public ingress, HTTPS only |
| User-assigned managed identity `id-agent-template-dev-api` | Used by `api` |
| PostgreSQL Flexible Server | Burstable `B1ms`, 32 GiB storage, backup retention 7 days, no HA, no geo-redundant backup; sizing re-checked against availability |
| Azure AI Foundry project + one model deployment | Model, capacity (TPM quota), and region chosen in the availability/cost check; capacity capped low; no live calls until approved |
| Consumption budget + alert rules | Monthly budget of USD 10 (real ceiling, see the cost check below; the earlier USD 50 figure no longer applies) with notifications; alerts may lag and are not a hard cap |

Identity and least privilege:

- The API runs as the user-assigned identity only. Roles: `AcrPull` on the
  registry, the Foundry data-plane user role scoped to the project, and
  PostgreSQL access through an Entra database role if supported (otherwise a
  secret in Key Vault, added only then). No subscription-wide or
  resource-group-wide Owner/Contributor for workloads.
- The web app needs no Azure data-plane identity.
- Key Vault is omitted unless a secret is unavoidable.
- The deploying human or later CI identity is outside this module.

Explicitly excluded: Front Door, API Management, VNet/private endpoints (cost
and network exposure decided in the review), zone redundancy, geo-replication,
Grafana/ELK, additional environments.

## Azure gate: subscription, region, quota and cost check (read-only, 2026-11)

Done with read-only `az` and the public Azure retail price API. Nothing was
created. Prices are list prices in USD and approximate.

Constraints that drive the design:

- Real budget: USD 10/month. Only one Azure environment exists: `dev`. CI/CD
  deploys to that same environment (an OIDC federated identity plus a GitHub
  Environment, not a second Azure environment). The state backend is shared
  bootstrap infrastructure, not an environment.
- Subscription state is `Enabled`. The quota/offer ID and spending limit are
  not exposed by the CLI (`null`); confirm credit balance and spend limit in
  the portal (manual step). No budgets exist yet. The signed-in user is Owner.
- Resource providers `Microsoft.App`, `Microsoft.ContainerRegistry`,
  `Microsoft.DBforPostgreSQL` and `Microsoft.OperationalInsights` are
  `NotRegistered` (`Microsoft.Storage`, `CognitiveServices`, `Consumption` and
  `CostManagement` are registered). Registration is a write, so it needs
  approval before the full deployment; Phase A needs none of them.

Region availability (PostgreSQL Flexible Server is the deciding factor):

| Region | PostgreSQL Flexible B1ms | Foundry `gpt-5.4-nano` |
| --- | --- | --- |
| `southcentralus` (closest to Houston) | Blocked: subscription restricted from provisioning | Yes (GlobalStandard 5000 K TPM, DataZoneStandard 2000 K TPM) |
| `eastus2` | Blocked: subscription restricted | Yes (same quotas) |
| `eastus`, `westus2` | Blocked | not checked |
| `centralus` (Iowa) | Available (`Standard_B1ms`) | Yes (same quotas) |
| `northcentralus`, `westus3` | Available | not checked |

Recommendation: `centralus`, the closest region that allows PostgreSQL.
Exceptions for the blocked regions need a support request ("Service and
subscription limits"); not worth it for this budget. Phase A (no PostgreSQL)
could run in `southcentralus` but keeping one region avoids a later move.

Model: `gpt-5.4-nano` (GA), deployment type `DataZoneStandard` (US data zone
processing; about 10% above GlobalStandard at roughly USD 0.22 per 1M input and
1.375 per 1M output tokens; GlobalStandard is USD 0.20 / 1.25 but may process
data in any region). Cap deployment capacity at 10 (10 K TPM) in Terraform. A
chat of 1,000 input plus 300 output tokens costs about USD 0.0006, so 1,000
chats are under USD 1. `gpt-4o-mini` and `o4-mini` are deprecating and
`gpt-4.1-nano` is legacy, so they are not recommended. Model access/terms may
need acceptance in the portal on first deployment.

Itemized monthly estimate for the current design in `centralus`:

| Resource | Estimate | Notes |
| --- | --- | --- |
| State storage account (bootstrap) | under USD 0.05 | A few KB of blobs, versioning/soft delete |
| Foundry project | USD 0 | No resource fee; pay per token |
| Model tokens (`gpt-5.4-nano`) | USD 0.1 to 1 | Personal/dev usage |
| Budget and alert | USD 0 | |
| Container Apps (Consumption, min replicas 0) | about USD 0 | Within monthly free grant (180 K vCPU-s, 360 K GiB-s, 2 M requests) for light use |
| Log Analytics / App Insights | USD 0 to 3 | First 5 GB/month free, then USD 2.76/GB; lower the planned 0.5 GB/day cap to 0.1 GB/day (0.5 GB/day could reach about USD 28) |
| Azure Container Registry Basic | about USD 5.1 | USD 0.1666/day, plus USD 0.10/GB storage |
| PostgreSQL Flexible B1ms, 32 GiB | about USD 18.2 | Compute 0.01921/h (about 14.0) plus storage 0.13/GiB (about 4.2); 7-day backups are covered by the free allotment |
| Full design total | about USD 24 to 27 | |

Fits in USD 10: state backend, Foundry project and model deployment, budget
and alert, Container Apps (idle), Application Insights with a low cap.
Does not fit: PostgreSQL B1ms alone (about USD 18) and, together with ACR,
the full design is about 2.5 times the budget. ACR (USD 5) fits only if
nothing else costs money.

Discrepancies between the design and the USD 10 budget:

- Budget resource of USD 50 must become USD 10 (updated above); alerts at
  50/80/100% of actual and 100% forecast. Alerts lag and are not a hard cap.
- PostgreSQL B1ms and ACR Basic exceed the budget as designed.
- App Insights daily cap of 0.5 GB is too high; use 0.1 GB.
- `eastus2` is unusable for PostgreSQL on this subscription.

### Phased variant that fits USD 10

Phase A (about USD 0.1 to 1/month): bootstrap state backend, one resource
group `rg-agent-template-dev`, Foundry project with one `gpt-5.4-nano`
`DataZoneStandard` deployment capped at 10 K TPM, and the USD 10 budget with
alerts. Test the real agent with the API running locally against the local
PostgreSQL container, authenticating to Foundry with the developer's
`az login` credential (`DefaultAzureCredential`) and the Foundry user role
scoped to the project. No container, registry, or hosted database exists.

Phase B (about USD 24 to 27/month, needs a larger budget or credit): add the
four resource providers, ACR, Container Apps environment and apps, managed
identity roles, PostgreSQL B1ms, Log Analytics and App Insights. Raise the
budget to match before applying. Stopping PostgreSQL when idle only helps for
up to 7 days at a time, so it is not a lasting saving.

### Manual steps for the user

- Confirm credits and the spend limit in the portal, since the CLI does not
  show them.
- Create or confirm the Entra External ID tenant and app registrations;
  Terraform here does not manage it.
- Accept any model terms on first deployment, and request quota if the
  deployment is rejected.
- Approve registering the four resource providers before Phase B.
- Create the GitHub Environment and approve the OIDC federated identity later
  (Phase 8).
- Data processing: choose `DataZoneStandard` (US) or `GlobalStandard`.

## Phase A code and reviewed plans (not applied)

Code: `bootstrap/` (state backend), `environments/dev/` (resource group,
Foundry project, one `gpt-5.4-nano` `DataZoneStandard` deployment capped at 10,
USD 10 budget with alerts at 50/80/100% actual and 100% forecast) and
`modules/foundry`, `modules/budget`. Each root has its own committed
`.terraform.lock.hcl` (copy of the root lock). No ACR, Container Apps,
PostgreSQL, or Application Insights (Phase B). `subscription_id` and
`budget_contact_emails` are variables (use `TF_VAR_subscription_id` and a
git-ignored `*.auto.tfvars`). Both providers set
`resource_provider_registrations = "none"`.

Plans were generated read-only on 2026-11-08 (local state, plan files outside
the repo; nothing applied, no model call). Static checks: `terraform fmt`,
`init -backend=false`, `validate`, and Checkov (7 findings skipped inline with
a reason: no private endpoints, customer-managed keys, or storage logging, all
out of budget; public network access stays on, access is Entra-only).

### Bootstrap plan: 5 to add, 0 to change, 0 to destroy

| Create | Notes |
| --- | --- |
| Resource group `rg-agent-template-tfstate` | `centralus` |
| Storage account `stagenttemplatetfstate` | GRS, TLS 1.2, HTTPS only, shared keys and local users off, OAuth default, no public blobs, infrastructure encryption, versioning, blob/container soft delete 14 days, name verified available |
| Container `tfstate` | private |
| Role assignment `Storage Blob Data Contributor` | scoped to the container, one per entry of `state_contributor_principal_ids` (plan used the operator) |
| Management lock `CanNotDelete` | on the storage account |

Sensitive: the account's access keys and connection strings are marked
sensitive but are unusable (shared keys disabled); no secret appears in code
or plan summary.

### Dev plan: 5 to add, 0 to change, 0 to destroy

| Create | Notes |
| --- | --- |
| Resource group `rg-agent-template-dev` | `centralus`, tag `environment = dev` |
| Foundry account `ai-agent-template-dev` | `AIServices` S0, project management on, local (key) auth disabled, system-assigned identity, public endpoint |
| Foundry project `proj-agent-template-dev` | system-assigned identity |
| Deployment `chat` | `gpt-5.4-nano` `2026-03-17`, `DataZoneStandard`, capacity 10, `NoAutoUpgrade` |
| Budget `budget-agent-template-dev` | USD 10 monthly from 2026-11-01, four notifications to the contact email (personal data, kept in the ignored tfvars) |

Sensitive: keys are disabled and never output; outputs are the endpoint,
project ID, and deployment name only.

### Required before apply (manual, human)

1. Confirm credits and spend limit in the portal.
2. Approve the bootstrap apply; the human runs it with local state from
   `bootstrap/` (`az login`, `TF_VAR_subscription_id`, an ignored tfvars with
   the operator object ID), then keeps or discards the local state knowingly.
3. Initialize dev with the backend values:
   `terraform init -backend-config="resource_group_name=rg-agent-template-tfstate" -backend-config="storage_account_name=stagenttemplatetfstate" -backend-config="container_name=tfstate"`,
   then re-run `plan` (the real dev plan runs against the remote backend) and
   approve it separately.
4. Accept the model terms and quota if the deployment is rejected.
5. The operator needs a Foundry data-plane role (for example Azure AI User on
   the project) to call the model locally; granting it is a later step.

## Provisioned (Phase A, applied 2026-11-08)

Applied by the operator with explicit approval. Subscription is otherwise
empty; nothing from Phase B exists. No model calls were made.

- Bootstrap (local state, git-ignored): resource group
  `rg-agent-template-tfstate`, storage account `stagenttemplatetfstate`
  (`centralus`, Standard_GRS, shared keys disabled, versioning and 14-day soft
  delete), container `tfstate`, `Storage Blob Data Contributor` on the
  container for the operator, `CanNotDelete` lock
  `lock-tfstate-cannot-delete`. Verified with `az`.
- Dev (remote state `dev/terraform.tfstate`): resource group
  `rg-agent-template-dev` (`centralus`), Foundry account
  `ai-agent-template-dev` (AIServices S0, keys disabled), project
  `proj-agent-template-dev`, deployment `chat` (`gpt-5.4-nano` `2026-03-17`,
  `DataZoneStandard`, capacity 10, succeeded), budget
  `budget-agent-template-dev` (USD 10 monthly), and a `Foundry User` role
  (the former "Azure AI User") on the project for the operator
  (`foundry_user_principal_ids`).
- State locking verified: a second `plan` during an `apply` failed with
  "state blob is already locked".
- Plan vs. approval: the dev plan was the reviewed 5 creates plus one role
  assignment (6 creates, 0 updates, 0 deletes). The first apply created the
  five and failed on the role name `Azure AI User` (not found by that name);
  the role is now `Foundry User` and the second apply added it.
- Local, git-ignored inputs: `TF_VAR_subscription_id` and
  `auto.local.auto.tfvars` in each root (`state_contributor_principal_ids`,
  `foundry_user_principal_ids`, `budget_contact_emails`).
- Local API against Foundry: endpoint output `foundry_endpoint`, deployment
  `chat`, credential `az login` (`DefaultAzureCredential`). The live adapter
  wiring is a later task.

## Phase A verification (read-only, 2026-11-08)

Checked with read-only `az` and `terraform plan` (no apply, no model call, no
changes). Subscription and principal IDs are omitted on purpose.

| Area | Evidence | Result |
| --- | --- | --- |
| Storage TLS | `minimumTlsVersion = TLS1_2`, `enableHttpsTrafficOnly = true` | OK |
| Storage keys | `allowSharedKeyAccess = false`, `defaultToOAuthAuthentication = true`, local users and SFTP off | OK |
| Storage exposure | `allowBlobPublicAccess = false`; `publicNetworkAccess = Enabled`, firewall default `Allow` | Accepted risk: every request needs an Entra token plus RBAC (no keys or SAS exist); no private endpoint (out of budget) |
| State durability | Versioning on, blob and container soft delete 14 days, `CanNotDelete` lock, infrastructure encryption; the blob has 15 versions and the current one is unleased | OK |
| State locking | Concurrent plan during apply failed with "state blob is already locked" (see Provisioned) | OK |
| Foundry TLS | Endpoint is HTTPS only (`https://ai-agent-template-dev.cognitiveservices.azure.com/`). Cognitive Services has no configurable minimum TLS property; Azure enforces TLS 1.2+ | OK (not tunable) |
| Foundry keys | `disableLocalAuth = true`; system-assigned identity; no keys exist or are output | OK |
| Foundry exposure | `publicNetworkAccess = Enabled`, no network ACLs. Anyone can reach the endpoint, but every call needs an Entra token with a data-plane role | Accepted risk for Phase A (local API); revisit with private endpoint or ACLs if budget allows |
| Model deployment | `chat`: `gpt-5.4-nano`, `DataZoneStandard`, capacity 10, `Succeeded` | OK |
| RBAC | Only two assignments exist for this project: `Storage Blob Data Contributor` on the `tfstate` container and `Foundry User` on the project, both for the operator user. No workload identity has Owner/Contributor | OK, least privilege |
| Operator privilege | The operator is Owner at subscription scope (the human who deploys; not a workload identity) | Note: consider a lesser role or PIM for daily use; required to create role assignments |
| Budget | `budget-agent-template-dev`: USD 10 monthly from 2026-11-01, notifications at 50/80/100% actual and 100% forecast, to the operator's email, all enabled; current spend USD 0 | OK (alerts lag, not a hard cap) |
| Secrets in git | `git log --all` shows no `*.tfstate`, `*.tfvars`, `.env`, or plan files ever added; `.gitignore` covers `*.tfstate`, `*.tfstate.*`, `*.tfplan`, `tfplan*`, `*.tfvars`; the operator email and subscription ID appear nowhere in tracked files | OK |
| Outputs | Dev outputs are endpoint, project ID, deployment name only | OK |
| Drift | `terraform plan` against the remote state: "No changes" | OK |

Local-only leftovers: `bootstrap/terraform.tfstate` and the `*.auto.local.auto.tfvars`
files are git-ignored. The bootstrap state holds no usable secret (shared keys
are disabled), but it is the only copy of the bootstrap state: back it up
privately or migrate it to the remote backend knowingly.

Not verifiable yet (no Container Apps, ACR, PostgreSQL, or App Insights exist):
health probes, API telemetry free of private data, and ingress TLS for the
apps. These moved to Phase B tasks in `tasks.md`.

## Phase B code and reviewed plan (not applied)

Code in `environments/dev`: `monitoring.tf` (Log Analytics + workspace-based
Application Insights, 0.1 GB/day cap, 30 days) and `apps.tf` (Container Apps
environment on Consumption, user-assigned identity
`id-agent-template-dev-api`, `Foundry User` for it on the project, Container
Apps `api` and `web`). Decisions: ADRs 0005, 0009 and 0010. This supersedes
the Phase B rows of the earlier design table (no ACR, no PostgreSQL, no Key
Vault; ACR/`AcrPull` and the 0.5 GB cap no longer apply).

Both apps: min replicas 0, max 2, external HTTPS ingress, liveness probes
(`/api/v1/health/live`, `/healthz`). `api` 0.5 vCPU / 1 GiB, `web` 0.25 vCPU /
0.5 GiB. Images come from `api_image` / `web_image` (default: a public
placeholder for the first apply; later GHCR tags or digests).

Inputs supplied outside git (`TF_VAR_*` or an ignored tfvars):
`ghcr_username`, `ghcr_read_token` (sensitive, `read:packages` only),
`database_url` (sensitive, Supabase session pooler,
`postgresql+psycopg://...`), and optionally `oidc_issuer`,
`oidc_discovery_url`, `oidc_audience`, `oidc_required_scope` (blank until the
Entra tenant exists; protected routes return 503 meanwhile).

Prerequisite (manual, needs approval): `Microsoft.App` and
`Microsoft.OperationalInsights` are `Unregistered` (`Microsoft.ManagedIdentity`
and `Microsoft.Insights` are registered). Provider registration is disabled in
Terraform, so register them first.

Plan (read-only against the remote state, dummy non-secret values for the
sensitive variables): **7 to add, 0 to change, 0 to destroy**; Phase A
resources untouched.

| Create | Notes |
| --- | --- |
| Log Analytics workspace `log-agent-template-dev` | PerGB2018, 30 days, 0.1 GB/day; shared keys sensitive |
| Application Insights `appi-agent-template-dev` | workspace-based, 0.1 GB/day, 30 days; connection string sensitive, not output |
| Container Apps environment `cae-agent-template-dev` | Consumption, no VNet |
| Identity `id-agent-template-dev-api` | used by `api` only |
| Role assignment `Foundry User` | API identity, scoped to the project |
| Container App `api` | secrets `database-url`, `ghcr-token` (sensitive) |
| Container App `web` | secret `ghcr-token` (sensitive) |

Checkov passes (16 passed, 7 skipped inline, 0 failed).

### Monthly cost estimate (list prices, USD, approximate)

| Item | Estimate | Notes |
| --- | --- | --- |
| Container Apps (Consumption, min 0) | about 0 | Inside the free grant (180 K vCPU-s, 360 K GiB-s, 2 M requests) for light use |
| Log Analytics ingestion | 0 | 0.1 GB/day is about 3 GB/month, under the 5 GB free |
| Application Insights ingestion | 0 | Same workspace and free grant; nothing is wired to it yet |
| Worst case, both caps hit every day | up to about 2 to 3 | 6 GB/month, about 1 GB billable at 2.76 |
| Identity, role assignment, environment | 0 | No fee |
| Model tokens (Phase A) | 0.1 to 1 | Pay per use |
| GHCR, Supabase | 0 | Outside Azure, free tiers |
| **Phase B added fixed cost** | **0** | |
| **Total with Phase A** | **about 0.1 to 4** | Under the USD 10 cap |

This meets the ADR 0002 rule of no new fixed monthly cost. Risks: a cap does
not stop Container Apps overage if traffic grows beyond the free grant, and
budget alerts lag.

## Phase B applied (dev)

Applied on 2026-11-08 from `environments/dev` after explicit user approval:
Log Analytics (0.1 GB/day cap, 30 days), Application Insights, the Container
Apps environment (Consumption), `id-agent-template-dev-api` with the Foundry
User role on the project, and the `api` and `web` Container Apps. The final
plan after apply reports no changes.

Verified with read-only checks: the resources exist in `rg-agent-template-dev`,
HTTP redirects to HTTPS (301) and TLS completes, the API identity holds only
Foundry User on the project, and the ingestion cap is in place.

Deployed state (2026-11-08): both apps run the real images published by CI
to GHCR, referenced by digest (set through `api_image` / `web_image` in the
ignored tfvars), and pull them with a read-only registry token. `GET
/api/v1/health/live` and `/ready` return 200 (readiness reaches the Supabase
session pooler), and the web app returns 200. Until the Entra External ID
tenant exists, `OIDC_*` is unset and protected routes are not usable.

- The secrets (`database-url`, registry token) hold the real values, supplied
  only through the git-ignored `auto.local.auto.tfvars`; they end up in the
  remote state (protected by Entra RBAC), never in git.
- Two `lifecycle { ignore_changes }` entries (`workload_profile` on the
  environment, `workload_profile_name` on the apps) stop Terraform from fighting
  the implicit "Consumption" profile Azure fills in. The environment also sets
  `logs_destination = "log-analytics"` explicitly.
- If `terraform apply` is interrupted, a stale state lock can remain; confirm no
  Terraform process is running, then `terraform force-unlock <id>`, and check
  Azure for resources created before the interruption (import them if needed).

## Images from CI (ADR 0011)

Pushes to `main` publish `ghcr.io/hgonza81/agent-template-api` and
`ghcr.io/hgonza81/agent-template-web` after the Trivy scan passes. Read the
digests from the `publish` job outputs (`api_image`, `web_image`) or the run
summary, then set `api_image` / `web_image` to those `...@sha256:...` values.
The web build reads the repository variables `VITE_API_BASE_URL` (default: the
dev API URL), `VITE_ENTRA_AUTHORITY`, `VITE_ENTRA_CLIENT_ID` and
`VITE_API_SCOPES` (default blank); these are public, not secrets.

## GitHub-to-Azure federation (dev)

Created on 2026-11-08 with the Azure CLI (ADR 0012); no client secret exists.

```sh
az ad app create --display-name agent-template-github-dev
az ad sp create --id <appId>
az ad app federated-credential create --id <appId> --parameters '{"name":"github-env-dev","issuer":"https://token.actions.githubusercontent.com","subject":"repo:hgonza81@143525276/agent-template@1447445745:environment:dev","audiences":["api://AzureADTokenExchange"]}'
az role assignment create --assignee-object-id <servicePrincipalObjectId> --assignee-principal-type ServicePrincipal --role Contributor --scope /subscriptions/<sub>/resourceGroups/rg-agent-template-dev
```

The GitHub Environment `dev` only deploys from `main` and holds the variables
`AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID` (not secrets).
Workflows authenticate with `azure/login` using OIDC (`id-token: write`) from a
job that declares `environment: dev`.

## Entra External ID tenant (dev)

Created on 2026-11-08 (ADR 0014): tenant `agenttemplate.onmicrosoft.com` in
`rg-agent-template-auth` through the ARM `ciamDirectories` API, then, as Global
Administrator of that tenant and through Microsoft Graph, the API registration
(scope `chat.use`), the SPA registration, admin consent and an email-and-password
sign-up/sign-in flow. The values live outside the repo: `OIDC_*` in the ignored
`auto.local.auto.tfvars` and `VITE_ENTRA_*` as GitHub repository variables.
Issuer: `https://<tenantId>.ciamlogin.com/<tenantId>/v2.0`; authority for the
SPA: `https://<tenantId>.ciamlogin.com/<tenantId>`. The tenant-ID form is required:
MSAL v5 checks that the issuer host in the discovery document matches the
authority host, so the name-based authority `https://agenttemplate.ciamlogin.com/`
fails with `endpoints_resolution_error` (the browser shows "We could not start
sign-in").

## Migration job and image updates (ADR 0017, not yet applied)

`azurerm_container_app_job.migrate` (`caj-agent-template-dev-migrate`) runs
`alembic -c alembic.ini upgrade head` from the API image in the same Container
Apps environment: manual trigger, 300 s timeout, no retries, 0.25 vCPU / 0.5 GiB,
no managed identity (no Azure permissions), only the `database-url` and registry
secrets plus `CORS_ALLOWED_ORIGINS` (required by the settings model).

Terraform ignores `template[0].container[0].image` on `api`, `web` and the job,
since CI deploys images with `az containerapp update`. `api_image` and
`web_image` are used only for the first apply or a recreation.

Run a migration (point the job at the image first if it changed):

```sh
RG=rg-agent-template-dev JOB=caj-agent-template-dev-migrate
az containerapp job update -g $RG -n $JOB --image ghcr.io/hgonza81/agent-template-api@sha256:<digest>
az containerapp job start -g $RG -n $JOB --query name -o tsv     # execution name
az containerapp job execution list -g $RG -n $JOB --query "[0].{name:name,status:properties.status}" -o table
```

Status ends as `Succeeded` or `Failed`. Logs (Log Analytics, a few minutes of
delay):

```sh
az monitor log-analytics query -w <workspaceCustomerId> --analytics-query \
  "ContainerAppConsoleLogs_CL | where ContainerJobName_s startswith 'caj-agent-template-dev-migrate' | project TimeGenerated, Log_s | order by TimeGenerated desc | take 50"
```

Plan on 2026-11-08 (read-only, remote state): 1 to add
(`azurerm_container_app_job.migrate`), 0 to change, 0 to destroy; Checkov 16
passed, 7 skipped, 0 failed. The apply is pending.

## Application Insights wiring and alerts (ADR 0019, plan only)

`apps.tf` passes the Application Insights connection string to `api` as the
Container Apps secret `appinsights-connection-string` (env
`APPLICATIONINSIGHTS_CONNECTION_STRING`). Retention (30 days) and the daily
cap (0.1 GB/day) are already set in `monitoring.tf`; no role is granted to
people (the connection string only allows ingestion). New in `monitoring.tf`:
action group `ag-agent-template-dev-ops` (email to `budget_contact_emails`)
and metric alerts `alert-agent-template-dev-api-5xx` (more than 5 5xx requests
in 15 minutes) and `alert-agent-template-dev-api-restarts` (more than 3
restarts in 15 minutes). Estimated fixed cost: about USD 0.10/month per
metric alert, about USD 0.20 total.

Plan (read-only, dummy secret values): 3 to add (action group and two
alerts), 1 to change (`api` secret and env; with dummy values it also shows
the dummy secrets differing), 0 to destroy. Checkov: 16 passed, 7 skipped,
0 failed. Pending: apply, deploying the new backend image through CI, and
verifying alert delivery.

## Telemetry and alert verification (dev, 2026-11-08)

- Phase B observability applied (ADR 0019): the API exports traces and metrics
  to Application Insights after CI deployed the new image. Data arrived
  (requests, dependencies, database operations) and queries for bearer tokens,
  registry tokens, connection strings and chat text over the exported records
  returned zero matches.
- Alert delivery: the action-group test API is not supported on this free
  subscription ("Free subscription not supported"), so delivery was verified
  with a temporary metric alert (`Requests > 0`, one-minute window) bound to the
  same action group. It fired, the owner confirmed the email arrived, and the
  rule was deleted right after. Terraform reports no
  drift.
- To repeat the check without Terraform: create a temporary metric alert on the
  API app with the action group `ag-agent-template-dev-ops`, send a few requests,
  confirm the email, and delete the rule.

## Phase B verification (dev, 2026-11-08)

Checked with read-only commands after the real images were deployed:

- TLS: both apps negotiate TLS 1.3 with a valid Microsoft-issued certificate,
  reject TLS 1.1, redirect HTTP to HTTPS (301) and have `allowInsecure=false`.
- Identity: the API runs as the user-assigned identity `id-agent-template-dev-api`
  whose only role is Foundry User on the Foundry project; the web app has no
  Azure identity. No workload identity holds Owner or Contributor.
- Probes: both apps have a platform liveness probe. There is deliberately no
  platform readiness probe (liveness must not depend on the database); readiness
  is checked by the deploy job's smoke tests (`/api/v1/health/ready`).
- Telemetry: API traces and metrics reach Application Insights and contain no
  tokens, credentials, connection strings or chat text.

Not verified: the call from the deployed API to Foundry with the managed
identity. It needs an authenticated chat request, which needs a signed-in user
in the Entra External ID tenant (manual check after signing up in the web app).

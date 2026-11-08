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

## Environment and state design (not yet provisioned)

Design only: nothing below exists in Azure until a reviewed plan is approved.

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

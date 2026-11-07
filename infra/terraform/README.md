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

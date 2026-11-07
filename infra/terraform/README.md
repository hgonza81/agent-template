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

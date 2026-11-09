# 0012. GitHub-to-Azure OIDC with a single `dev` deploy identity

- Status: accepted
- Date: 2026-11-08

## Context

CI/CD needs to deploy to Azure without long-lived credentials. The repository
is public, so the trust between GitHub and Azure must not be reachable from
forks or arbitrary branches.

## Decision

- One Entra app registration, `agent-template-github-dev`, with a federated
  credential (no client secret) for the exact subject
  `repo:hgonza81@143525276/agent-template@1447445745:environment:dev`, issuer
  `https://token.actions.githubusercontent.com`.
- The GitHub Environment `dev` only accepts deployments from `main`
  (deployment branch policy). Jobs get Azure access only by running in that
  environment.
- The identity holds `Contributor` scoped to `rg-agent-template-dev` only. It
  is simple and enough to update the Container Apps; it cannot reach the state
  backend, other resource groups or role assignments at subscription level.
- The IDs (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`) are
  GitHub Environment variables, not secrets.
- `terraform apply` stays manual (run by the owner); CI uses this identity only
  to deploy images.

## Consequences

- No Azure credentials are stored in GitHub. Revoking access is deleting the
  federated credential or the role assignment.
- `Contributor` on the resource group is broader than strictly necessary (it
  could change any resource there). A narrower custom role is a later
  improvement once the deploy steps are stable.
- The identity was created with the Azure CLI, not Terraform; the commands are
  recorded in `infra/terraform/README.md` so it can be recreated.
- A read-only identity for Terraform plan jobs is a separate, later task.

## Update (2026-11-08)

The first deploy failed with `AADSTS700213` because this repository's OIDC
subject uses numeric IDs, not names:
`repo:hgonza81@143525276/agent-template@1447445745:environment:dev`. The federated
credential was updated to that exact subject. If the repository is renamed or
recreated, the subject changes and the credential must be updated again.

# 0016. No Terraform plan job in CI for now

- Status: accepted
- Date: 2026-11-08

## Context

`tasks.md` asks that Terraform plan jobs be read-only, expose only a redacted
summary and never publish state or plan binaries. A useful plan job needs real
variable values (database URL, registry token) and read access to the state, and
the Container Apps provider also reads secrets, which a plain `Reader` role
cannot do. A plan with placeholder values would always report spurious changes.

## Decision

Keep CI as it is: `fmt`, `init -backend=false`, `validate` and Checkov, with no
Azure credentials and no state access. Plans and applies run locally by the
owner, with the secrets in the ignored `auto.local.auto.tfvars`. The requirement
is met because no CI job can write to Azure through Terraform.

## Consequences

- Nothing in CI can change or read Azure state; the deploy identity (ADR 0012)
  is used only to deploy images.
- If a plan job is added later it must use a separate read-only identity bound
  to its own GitHub Environment, run with `-lock=false`, publish only counts and
  resource addresses in the job summary, and upload no state or plan files.

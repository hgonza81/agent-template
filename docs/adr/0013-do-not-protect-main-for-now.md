# 0013. Do not protect `main` for now

- Status: accepted
- Date: 2026-11-08

## Context

`tasks.md` asked to gate applies and deployments with GitHub Environment
approvals and protected branches. This is a solo learning project where the
workflow is committing directly to `main` (see `AGENTS.md`). Branch protection
would force pull requests or block pushes.

## Decision

No branch protection, no required reviewers and no required PRs on `main`. The
only gate kept is the one that costs nothing and removes real risk: the GitHub
Environment `dev` deploys only from `main` (deployment branch policy), and the
Azure federated credential is bound to that environment (ADR 0012).

## Consequences

- A push to `main` can publish images; deploying them to Azure is still a
  separate step bound to the `dev` environment.
- The repository is public, so anyone can read the code but only the owner can
  push. Pull requests from forks never receive Azure tokens.
- Protection rules, required checks and PR workflows can be added later on a
  separate branch for experimentation, by the owner's choice.

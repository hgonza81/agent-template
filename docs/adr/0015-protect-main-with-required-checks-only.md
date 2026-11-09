# 0015. Protect `main` with required checks only

- Status: accepted
- Date: 2026-11-08
- Supersedes: [0013](0013-do-not-protect-main-for-now.md)

## Context

ADR 0013 chose no branch protection. The owner then asked for the lighter
option: required status checks without pull requests or approvals, keeping the
direct-push workflow from `AGENTS.md`.

## Decision

Branch protection on `main` requires the CI jobs `backend`, `frontend`,
`terraform` and `secrets` to pass before merging, with no required pull request
or review, `strict` off, force pushes and branch deletion disabled, and
`enforce_admins` off.

## Consequences

- The owner is an administrator, so direct pushes keep working: with admin
  enforcement off, the required checks gate merges of pull requests but do not
  block the owner's own pushes. Checks cannot gate a direct push anyway, since a
  new commit has no check results yet.
- Force pushes to `main` are now blocked. Rewriting history (as was done once to
  remove co-author lines) requires temporarily lifting the protection.
- Matrix jobs (`containers`) and `publish` are not required checks: `publish`
  only runs on `main`.
- The `dev` environment still deploys only from `main` (ADR 0012).

# Architecture Decision Records

Short records of decisions that shape the project, so the reasoning survives
after the conversation that produced it. One file per decision:
`NNNN-short-title.md`, numbered in order, never renumbered.

## When to write one

Write an ADR whenever a decision is made that is hard to reverse, changes the
design, costs money, moves something outside Azure, or resolves a real
dilemma between options. Small, obvious choices do not need one.

## Format

```markdown
# NNNN. Title

- Status: proposed | accepted | superseded by NNNN
- Date: YYYY-MM-DD

## Context
What forced the decision, and the options considered.

## Decision
What was chosen and why this option over the others.

## Consequences
What gets easier, what gets harder, and what to revisit later.
```

Do not edit an accepted ADR to change the decision: add a new one that
supersedes it and update the old one's status.

## Index

- [0001](0001-record-decisions-and-prefer-the-simplest-solution.md): Record decisions as ADRs; prefer the simplest decent solution
- [0002](0002-single-dev-environment-on-azure-within-a-usd-10-budget.md): One Azure `dev` environment within a USD 10 monthly budget
- [0003](0003-keep-conversation-history-in-foundry-threads.md): Keep conversation history in Foundry threads
- [0004](0004-call-foundry-through-the-openai-sdk-with-the-project-endpoint.md): Call Foundry through the `openai` SDK with the project endpoint 
- [0005](0005-use-supabase-for-postgresql.md): Use Supabase for PostgreSQL
- [0006](0006-pin-provider-library-loggers-to-warning.md): Pin provider and HTTP library loggers to WARNING
- [0008](0008-delete-the-provider-conversation-before-the-subscription.md): Delete the provider conversation before the subscription
- [0009](0009-use-github-container-registry-for-images.md): Use GitHub Container Registry for images
- [0010](0010-expose-the-api-externally-and-defer-application-insights-wiring.md): Expose the API externally and defer Application Insights wiring
- [0011](0011-publish-the-scanned-images-from-main-and-reference-them-by-digest.md): Publish the scanned images from main and reference them by digest
- [0012](0012-github-to-azure-oidc-with-a-single-dev-deploy-identity.md): GitHub-to-Azure OIDC with a single `dev` deploy identity
- [0013](0013-do-not-protect-main-for-now.md): Do not protect `main` for now (superseded by 0015)
- [0014](0014-entra-external-id-tenant-created-through-the-azure-api.md): Entra External ID tenant created through the Azure API
- [0015](0015-protect-main-with-required-checks-only.md): Protect `main` with required checks only (supersedes 0013)
- [0016](0016-no-terraform-plan-job-in-ci-for-now.md): No Terraform plan job in CI for now
- [0017](0017-run-migrations-in-a-manual-container-apps-job.md): Run migrations in a manual Container Apps job

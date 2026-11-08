# 0002. One Azure `dev` environment within a USD 10 monthly budget

- Status: accepted
- Date: 2026-11-08

## Context

The original design assumed a USD 50/month ceiling. The owner's real budget is
USD 10/month, set as a spending limit on the subscription. The itemized
estimate for the full design was about USD 24-27/month, dominated by
PostgreSQL Flexible Server B1ms (~USD 18) and Azure Container Registry Basic
(~USD 5). PostgreSQL Flexible Server is also restricted in this subscription
for `eastus2`, `eastus`, `southcentralus` and `westus2`.

## Decision

- Only one Azure environment, `dev`. No staging, no production for now. CI/CD
  will use `dev` through OIDC federation and a GitHub Environment, not a
  separate Azure environment.
- Region `centralus`, the closest to Houston that allows the resources needed.
- Model `gpt-5.4-nano`, `DataZoneStandard` (US data processing), capacity
  capped at 10.
- Phase A (deployed): Terraform state backend, `dev` resource group, Foundry
  project and one model deployment, USD 10 budget with alerts. Pay-per-use
  only.
- Phase B (not deployed): container hosting, registry, database, monitoring.
  Not created until each fixed cost is checked against the rules below.
- Cost rules: avoid fixed monthly costs; up to USD 10/month of fixed cost is
  tolerated for now, but because the whole cap is USD 10, any fixed cost must
  be flagged first. Azure AI Foundry stays on Azure. Prefer Azure for the rest;
  if a component has a high fixed cost, decide with the owner whether to host it
  elsewhere (for example a free-tier PostgreSQL or GitHub Container Registry).

## Consequences

- The PostgreSQL-on-Azure assumption in `plan.md` is open until Phase B.
- Budget alerts lag and are not a hard cap; the subscription spending limit is
  the real guard.
- Anything above the cost rules needs an explicit decision, recorded as a new
  ADR.

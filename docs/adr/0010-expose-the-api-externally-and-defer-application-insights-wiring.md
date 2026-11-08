# 0010. Expose the API externally and defer Application Insights wiring

- Status: accepted
- Date: 2026-11-08

## Context

Phase B hosts `web` and `api` on Azure Container Apps (Consumption). The SPA
runs in the browser and calls the API directly, so the API must be reachable
from the internet. An internal-only ingress needs a VNet-integrated
environment, which is outside the budget and the simplest-solution rule
(ADRs 0001, 0002). The API also exports OTLP, which Application Insights does
not ingest directly without extra components.

## Decision

- `api` has external HTTPS ingress (HTTP disallowed). Authorization is
  enforced in FastAPI by validating the Entra JWT on every protected route;
  CORS allows only the `web` origin. `web` is external HTTPS too.
- Secrets (`database-url`, GHCR read token) are Container Apps secrets passed
  as sensitive Terraform variables outside git. No Key Vault and no ACR.
  Foundry access uses the user-assigned identity (`Foundry User` on the
  project, `AZURE_CLIENT_ID` set for `DefaultAzureCredential`).
- Log Analytics and Application Insights are created with a 0.1 GB/day cap and
  30-day retention, but the API is not wired to Application Insights yet; the
  Container Apps environment logs go to Log Analytics. Wiring (OTLP to the
  Container Apps managed agent or the Azure Monitor exporter) is a later task
  and must keep chat content out of telemetry.
- Until the images are published, both apps default to a public placeholder
  image so the first apply can succeed.

## Consequences

- No fixed Azure cost is added; costs stay in free grants for light use.
- The API is publicly reachable; rate limits and JWT validation are the
  protection. Revisit if an internal topology becomes affordable.
- Scale to zero means cold starts on the first request.
- The Phase B telemetry verification task cannot pass until the wiring exists.

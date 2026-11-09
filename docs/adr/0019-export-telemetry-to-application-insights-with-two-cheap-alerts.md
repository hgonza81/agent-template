# 0019. Export telemetry to Application Insights with two cheap alerts

- Status: accepted
- Date: 2026-11-08

## Context

ADR 0010 deferred wiring Application Insights. The API already has
privacy-filtered OpenTelemetry traces and metrics (optional local OTLP).
ADR 0002 caps fixed costs: the total budget is USD 10.

## Decision

- The API exports to Application Insights with
  `azure-monitor-opentelemetry-exporter` when
  `APPLICATIONINSIGHTS_CONNECTION_STRING` is set, reusing the existing
  instrumentation and the same allowlist filters (wrapped around the Azure
  exporters, so chat content, tokens, URLs, SQL and exception details are
  never sent). It coexists with OTLP; without either variable telemetry is
  off. Statsbeat and offline disk storage are disabled. The simpler distro
  was not used: it would replace the existing providers and filters.
- Terraform passes the connection string as the Container Apps secret
  `appinsights-connection-string` and the env var of the same purpose.
- Access: no new role is granted to anyone. The connection string only allows
  ingestion. Retention stays 30 days and the daily cap 0.1 GB/day.
- Alerts: one action group `ag-agent-template-dev-ops` (email to
  `budget_contact_emails`) and two metric alerts on the `api` Container App:
  more than 5 `5xx` requests in 15 minutes, and more than 3 container
  restarts in 15 minutes.

## Consequences

- Estimated fixed cost: about USD 0.10/month per metric alert (about USD 0.20
  total); email notifications are free at this volume. Ingestion stays inside
  the free grant and the cap.
- Alerts need traffic or restarts to fire; delivery is verified manually after
  apply by the owner.
- The new image must be deployed (CI) for the API to start exporting.

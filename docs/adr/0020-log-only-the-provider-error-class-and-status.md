# 0020. Log only the provider error class and HTTP status

- Status: accepted
- Date: 2026-11-08

## Context

The first end-to-end test in dev returned 503 on chat with a log that only said
`http_error`, so the cause (credential, RBAC, endpoint, deployment) was not
diagnosable. Provider exception messages and bodies can echo prompts, output or
tokens (see ADR 0006), so they cannot be logged.

Also, the Azure Monitor trace exporter read the global tracer provider, which is
a resource-less proxy because the app keeps its own provider unregistered.

## Decision

- `AgentError` carries `provider_error_type` (exception class name) and
  `provider_status` (integer `status_code` if present). The request log line and
  span get these two fields only; the HTTP response stays generic.
- Pass the app's `TracerProvider` to `AzureMonitorTraceExporter`
  (`tracer_provider=`) instead of registering a global provider, which would
  change instrumentation behaviour for every library.

## Consequences

- Failures are classified without leaking content; richer detail needs a new
  decision.
- The two span attributes are added to the telemetry allowlist.

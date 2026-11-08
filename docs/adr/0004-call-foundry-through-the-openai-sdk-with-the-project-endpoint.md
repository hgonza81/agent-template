# 0004. Call Foundry through the `openai` SDK with the project endpoint

- Status: accepted
- Date: 2026-11-08

## Context

The backend needs one server-side way to send a message to the `chat`
deployment and keep a per-user conversation. The Foundry resource endpoint
(`*.cognitiveservices.azure.com`, path `/openai/v1/`) returned 404 for the
Conversations API in a diagnostic call; only the project endpoint
(`*.services.ai.azure.com/api/projects/<project>`) works for it.

## Decision

- Use the `openai` SDK (Conversations and Responses APIs) against the project
  endpoint, with `azure-identity` `DefaultAzureCredential` and token scope
  `https://ai.azure.com/.default`. No keys.
- Configuration through `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_DEPLOYMENT`.
- Plain agent: no instructions, tools or retrieval. No retries
  (`max_retries=0`) to keep cost and behavior predictable.
- `AGENT_PROVIDER` is `fake` by default; `foundry` is opt-in and the backend
  fails at startup if its settings are missing, never falling back silently.

## Consequences

- Tests use an injected fake client and never touch the network; the real
  integration was verified once manually with a minimal call.
- Two new dependencies (`azure-identity`, `openai`), kept clean by
  `make audit`.
- The app code is tied to the Conversations API shape; if the provider API
  changes, only the client module needs to change.

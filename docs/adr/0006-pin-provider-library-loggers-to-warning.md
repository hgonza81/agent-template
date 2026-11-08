# 0006. Pin provider and HTTP library loggers to WARNING

- Status: accepted
- Date: 2026-11-08

## Context

The privacy tests for the Foundry adapter showed that the `openai` SDK logs
`Request options` including the full JSON body (the user's prompt) at DEBUG.
Other libraries (`httpx`, `httpcore`, `azure`, `msal`) log URLs and headers at
low levels. Raising the app log level to DEBUG, or setting `OPENAI_LOG=debug`,
would then leak chat content into logs.

## Decision

`configure_logging` pins `openai`, `httpx`, `httpcore`, `azure` and `msal`
loggers to WARNING regardless of the root level. This is the simplest fix; a
custom redacting log filter was rejected as more code and easier to bypass.

## Consequences

- Chat content cannot reach logs through these libraries at DEBUG.
- Useful library diagnostics are unavailable unless someone deliberately
  changes the code; revisit only with a redaction strategy.
- `backend/tests/test_chat_privacy.py` guards this with the real adapter over a
  fake transport.

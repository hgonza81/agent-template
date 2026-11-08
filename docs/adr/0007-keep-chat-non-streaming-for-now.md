# 0007. Keep chat non-streaming for now

- Status: accepted
- Date: 2026-11-08

## Context

The plan prefers streaming (Server-Sent Events) only if cancellation, cleanup
on client disconnect, and testability are reliable. A focused spike used the
current stack (FastAPI 0.162, Starlette 1.10), a `StreamingResponse` over an
async generator with `try/finally`, and a raw ASGI client that sends
`http.disconnect` after the third chunk. No network, no model calls.

Evidence from the spike:

- Cancellation works: the stream stopped after 3 of 1000 chunks.
- Cleanup works: the generator's `finally` ran on disconnect.
- It is testable deterministically in CI: driving the ASGI app directly with a
  scripted `receive`/`send` needs no sockets, sleeps are short, and a timeout
  guards hangs.

Not proven by the spike (and not provable without real calls): that the
`openai` SDK's streaming Responses call to Foundry is cancelled and its HTTP
connection released when the generator is closed. Streaming would also need a
new agent interface, a decision on persisting partial replies when the client
drops (the Foundry thread holds the history, ADR 0003), an SSE client in the
frontend, a changed OpenAPI contract, and rework of the size, limit and
privacy tests. The chat today is a bounded, non-streaming response that is
already implemented and tested.

## Decision

Keep the non-streaming `POST /chat/messages`. Streaming is a documented future
improvement, not part of the first release. The simplest option that meets the
spec wins; the spec allows "return or stream".

## Consequences

- No API, frontend, or test changes; no spike code is kept.
- Users wait for the full (bounded) reply instead of seeing tokens arrive.
- If streaming is revisited: reuse the spike approach (`StreamingResponse`
  with `try/finally`, deterministic ASGI-level disconnect test), first verify
  against the real adapter that closing the stream releases the provider
  connection, define partial-reply persistence, and regenerate API types.

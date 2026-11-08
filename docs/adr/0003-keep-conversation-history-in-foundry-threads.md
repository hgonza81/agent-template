# 0003. Keep conversation history in Foundry threads

- Status: accepted
- Date: 2026-11-08

## Context

`plan.md` assumes Foundry Agent Service owns the thread and message history and
the app only stores `foundry_thread_id` on `subscriptions`. What is deployed so
far is only a model (`gpt-5.4-nano`), so it is not yet verified that threads
work with this subscription and what retention they have. The alternative is to
store messages ourselves, which adds a messages table and code, and its home
depends on the still-open database decision (see ADR 0002).

## Decision

Keep the existing design: Foundry threads hold the history, the app stores
only the thread reference. It is the simplest option because the data model,
the privacy posture (no chat content in our database) and the adapter shape
already assume it.

## Consequences

- Verified on 2026-11-08: a live call against the `dev` project created a
  Foundry conversation through the Conversations API and got a model reply, so
  server-side history works with this subscription (see ADR 0004).
- The provider's retention and deletion behavior is still to be verified
  before production (tracked in `tasks.md`); if it is unacceptable, supersede
  this ADR with one that stores messages ourselves.
- No messages table, so no chat content in our database or backups.

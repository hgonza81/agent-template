# 0008. Delete the provider conversation before the subscription

- Status: accepted
- Date: 2026-11-08

## Context

`spec.md` requires account deletion to remove the subscription and its Foundry
conversation (see ADR 0003). The conversation lives only at the provider and
is referenced from the `subscriptions` row. Deleting the row first would leave
an unreachable, orphaned conversation if the provider call then failed.

## Decision

`DELETE /api/v1/me` locks the caller's row, deletes the provider conversation
(`conversations.delete`; a 404 is treated as already deleted), and only then
deletes the row. A provider failure keeps the row so the request can be
retried. No separate cleanup job or soft-delete state was added.

## Consequences

- Retries are safe and no orphaned conversations are created by deletion.
- If the provider deletes but the database commit fails, the next retry gets a
  404, treats it as success, and removes the row.
- Provider-side retention after deletion is still to be verified before
  production (tracked in `tasks.md`).

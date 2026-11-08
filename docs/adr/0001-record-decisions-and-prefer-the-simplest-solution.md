# 0001. Record decisions as ADRs; prefer the simplest decent solution

- Status: accepted
- Date: 2026-11-08

## Context

The project is built incrementally, by one person with AI agents, over many
sessions. Decisions made in chat are lost, and without a rule for dilemmas the
design tends to grow more complex than the MVP needs.

## Decision

- Record significant decisions as ADRs in `docs/adr/` (see the README there).
- When two options are both acceptable, choose the simplest one that is decent
  and improve it later if needed. Do not build for hypothetical future needs.
  Complexity must be justified by a present requirement.

## Consequences

- Agents must write or update an ADR for each significant decision they take,
  and mention it in the commit.
- Some choices will be revisited later; that is expected and cheap compared
  with over-engineering now.

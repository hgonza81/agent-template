# 0005. Use Supabase for PostgreSQL

- Status: accepted
- Date: 2026-11-08

## Context

Azure Database for PostgreSQL Flexible Server B1ms costs about USD 18/month
fixed, above the USD 10 monthly cap (ADR 0002), and is restricted in several
regions of this subscription. The owner chose Supabase as the PostgreSQL host.
Only the `subscriptions` table lives in it (ADR 0003: no chat content).

## Decision

Host PostgreSQL on Supabase. The app keeps talking plain PostgreSQL through
SQLAlchemy and Alembic, so this is a connection-string change, not a code
change. Azure AI Foundry stays on Azure.

## Consequences

- No Azure database fixed cost. Local development keeps using the Docker
  PostgreSQL.
- The connection string is a secret: it must never be committed or logged, and
  needs a safe place when the API is deployed (decided in Phase B, simplest
  option first).
- To verify before relying on it: the free plan's limits and inactivity
  pausing, required TLS settings, and which connection mode (direct or pooled)
  works with the migrations and the async/concurrency behavior.
- Subscription records (issuer, subject, display email) are stored by a third
  party outside Azure; this is acceptable because it holds no chat content.
- Terraform does not manage the database; the Phase B Azure design drops
  PostgreSQL Flexible Server.

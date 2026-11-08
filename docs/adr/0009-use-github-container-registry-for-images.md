# 0009. Use GitHub Container Registry for images

- Status: accepted
- Date: 2026-11-08

## Context

Azure Container Registry Basic costs about USD 5/month fixed. The owner wants
to avoid fixed costs (ADR 0002) and chose GitHub Container Registry (GHCR),
which has no fixed fee for this use and already sits next to the CI.

## Decision

Publish the frontend and API images to GHCR, referenced by commit SHA or
digest. Azure Container Apps pulls them with a registry credential.

## Consequences

- No Azure registry fixed cost; the Phase B design drops Azure Container
  Registry.
- Pulling a private image from Azure needs a credential (a token with only
  `read:packages`), which is a secret to store as a Container Apps secret and
  rotate. Simplest first: keep images private and use that token; making the
  images public would remove the secret but exposes the code, so it is a later
  choice if the repository becomes public.
- CI publishes with the workflow's own `GITHUB_TOKEN` (`packages: write`) only
  from trusted refs, never from untrusted pull requests.
- The identity-based `AcrPull` role in the earlier design no longer applies.

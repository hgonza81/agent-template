# 0011. Publish the scanned images from main and reference them by digest

- Status: accepted
- Date: 2026-11-08

## Context

ADR 0009 chose GHCR. The CI `containers` job already builds and Trivy-scans both
images. We need to publish exactly the scanned images, only from trusted code,
so a later deployment promotes the same artifacts.

## Decision

- The `containers` job builds each image once, tagged `<image>:<commit SHA>`,
  scans it (HIGH/CRITICAL fixable findings fail the build) and, on pushes to
  `main` only, uploads it as a one-day workflow artifact (`docker save`).
- A separate `publish` job (`needs: containers`, `if` push to `main`,
  `packages: write`, `GITHUB_TOKEN`, no Azure credentials) loads those tarballs
  and pushes them without rebuilding. It outputs `api_image` and `web_image` as
  `ghcr.io/hgonza81/<name>@sha256:...` and lists them in the run summary.
- Images: `ghcr.io/hgonza81/agent-template-api` and
  `ghcr.io/hgonza81/agent-template-web`. Deployments use the digest reference
  (Terraform `api_image` / `web_image`), not a mutable tag.
- Frontend `VITE_*` values are public build args read from repository
  variables (`vars`, not secrets): `VITE_API_BASE_URL` (defaults to the dev API
  URL), `VITE_ENTRA_AUTHORITY`, `VITE_ENTRA_CLIENT_ID`, `VITE_API_SCOPES`
  (default blank).

## Consequences

- Pull requests and forks never get `packages: write` and never publish.
- The artifact hand-off keeps "scanned image = published image" without extra
  tooling; the cost is a short-lived artifact per image.
- The web image is built for one environment (dev) because the values are baked
  in; another environment needs a rebuild with other variables.

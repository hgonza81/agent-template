#!/usr/bin/env bash
# Build both images and verify them locally: non-root user, health checks,
# readiness vs liveness, SPA fallback, and graceful shutdown. Needs Docker only.
set -euo pipefail
cd "$(dirname "$0")/.."

API_IMAGE=agent-template-api:test
WEB_IMAGE=agent-template-web:test
api=agent-template-api-test
web=agent-template-web-test

cleanup() { docker rm -f "$api" "$web" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

fail() { echo "FAIL: $*" >&2; exit 1; }

wait_healthy() {
  for _ in $(seq 1 40); do
    status=$(docker inspect --format '{{.State.Health.Status}}' "$1")
    [ "$status" = healthy ] && return 0
    sleep 2
  done
  docker logs "$1" >&2 || true
  fail "$1 did not become healthy"
}

assert_graceful_stop() {
  local name=$1 started stopped code
  started=$(date +%s)
  docker stop --time 30 "$name" >/dev/null
  stopped=$(date +%s)
  code=$(docker inspect --format '{{.State.ExitCode}}' "$name")
  [ "$code" = 0 ] || fail "$name exited with $code on SIGTERM (expected 0)"
  [ $((stopped - started)) -lt 20 ] || fail "$name took too long to stop"
}

docker build -q -t "$API_IMAGE" backend >/dev/null
docker build -q -t "$WEB_IMAGE" frontend >/dev/null

for image in "$API_IMAGE" "$WEB_IMAGE"; do
  user=$(docker inspect --format '{{.Config.User}}' "$image")
  [ -n "$user" ] && [ "$user" != root ] && [ "$user" != 0 ] \
    || fail "$image does not run as a non-root user"
done

# API: PostgreSQL is intentionally unreachable, so liveness must stay healthy
# while readiness reports unavailable.
docker run -d --name "$api" -p 127.0.0.1:18000:8000 \
  -e CORS_ALLOWED_ORIGINS='["http://127.0.0.1:5173"]' \
  -e DATABASE_URL='postgresql+psycopg://agent_template:x@127.0.0.1:1/agent_template' \
  "$API_IMAGE" >/dev/null
wait_healthy "$api"
[ "$(docker exec "$api" id -u)" = 10001 ] || fail "API process is not uid 10001"
curl -fsS http://127.0.0.1:18000/api/v1/health/live >/dev/null || fail "API liveness"
ready=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18000/api/v1/health/ready)
[ "$ready" = 503 ] || fail "API readiness returned $ready without a database (expected 503)"
docker exec "$api" alembic heads >/dev/null || fail "migrations are missing from the API image"
assert_graceful_stop "$api"

# Frontend: static files, SPA fallback, health endpoint.
docker run -d --name "$web" -p 127.0.0.1:18080:8080 "$WEB_IMAGE" >/dev/null
wait_healthy "$web"
[ "$(docker exec "$web" id -u)" != 0 ] || fail "web process runs as root"
curl -fsS http://127.0.0.1:18080/healthz >/dev/null || fail "web health endpoint"
curl -fsS http://127.0.0.1:18080/ | grep -q '<div id="root"' || fail "index.html not served"
curl -fsS http://127.0.0.1:18080/chat | grep -q '<div id="root"' || fail "SPA fallback"
assets=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/assets/missing.js)
[ "$assets" = 404 ] || fail "missing asset returned $assets (expected 404)"
assert_graceful_stop "$web"

echo "Container checks passed."

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.local-test"
ENV_EXAMPLE="$ROOT_DIR/.env.local-test.example"
COMPOSE_FILE="$ROOT_DIR/docker-compose.local-test.yml"
PROJECT_NAME="aqc-local-test"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created $ENV_FILE from .env.local-test.example"
fi

set -a
source "$ENV_FILE"
set +a

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required." >&2
  exit 1
fi

"${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d --build db api

API_PORT="${LOCAL_TEST_API_PORT:-18080}"
echo "Waiting for local test API on http://127.0.0.1:${API_PORT}/api/health ..."

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then
    echo "Local test API is ready."
    echo
    echo "Next step:"
    echo "  ./scripts/local-test-frontend.sh"
    echo
    echo "Test login:"
    echo "  account: ${ADMIN_USERNAME:-La}"
    echo "  password: ${ADMIN_PASSWORD:-change-this-local-password}"
    exit 0
  fi
  sleep 2
done

echo "Local test API did not become ready in time. Showing recent API logs:" >&2
"${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs --tail=120 api >&2
exit 1

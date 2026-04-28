#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.local-test"
ENV_EXAMPLE="$ROOT_DIR/.env.local-test.example"
COMPOSE_FILE="$ROOT_DIR/docker-compose.local-test.yml"
PROJECT_NAME="aqc-local-test"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required." >&2
  exit 1
fi

if [ "${1:-}" = "--reset" ]; then
  "${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v
  echo "Local test system stopped and test database volume removed."
else
  "${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
  echo "Local test system stopped. Test database volume is preserved."
fi

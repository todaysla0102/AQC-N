#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.local-test"
ENV_EXAMPLE="$ROOT_DIR/.env.local-test.example"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created $ENV_FILE from .env.local-test.example"
fi

set -a
source "$ENV_FILE"
set +a

API_PORT="${LOCAL_TEST_API_PORT:-18080}"
FRONTEND_PORT="${LOCAL_TEST_FRONTEND_PORT:-5173}"

cd "$ROOT_DIR/client"

VITE_API_BASE="http://127.0.0.1:${API_PORT}/api" \
VITE_LOCAL_TEST_LOGIN=true \
VITE_LOCAL_TEST_ACCOUNT="${ADMIN_USERNAME:-La}" \
npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"

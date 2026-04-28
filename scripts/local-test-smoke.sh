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
API_BASE="http://127.0.0.1:${API_PORT}/api"

curl -fsS "${API_BASE}/health" >/dev/null

LOGIN_RESPONSE="$(
  curl -fsS "${API_BASE}/auth/local-login" \
    -H "Content-Type: application/json" \
    --data "{\"account\":\"${ADMIN_USERNAME:-La}\",\"password\":\"${ADMIN_PASSWORD:-change-this-local-password}\"}"
)"

case "$LOGIN_RESPONSE" in
  *'"success":true'*)
    echo "Smoke test passed: health check and local login are OK."
    ;;
  *)
    echo "Smoke test failed: local login did not return success." >&2
    echo "$LOGIN_RESPONSE" >&2
    exit 1
    ;;
esac

#!/usr/bin/env bash

set -euo pipefail

LOG_FILE="${LOG_FILE:-/var/log/docker-safe-prune.log}"
LOCK_FILE="${LOCK_FILE:-/var/run/docker-safe-prune.lock}"

# Keep a short buffer for dangling build leftovers and a longer buffer for
# tagged images so recent rollbacks stay available for a while.
DANGLING_UNTIL="${DANGLING_UNTIL:-24h}"
UNUSED_IMAGE_UNTIL="${UNUSED_IMAGE_UNTIL:-168h}"
BUILDER_CACHE_UNTIL="${BUILDER_CACHE_UNTIL:-168h}"
STOPPED_CONTAINER_UNTIL="${STOPPED_CONTAINER_UNTIL:-168h}"

PRUNE_STOPPED_CONTAINERS="${PRUNE_STOPPED_CONTAINERS:-1}"
PRUNE_UNUSED_NETWORKS="${PRUNE_UNUSED_NETWORKS:-0}"

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi

exec >>"$LOG_FILE" 2>&1

timestamp() {
  date '+%Y-%m-%d %H:%M:%S %z'
}

run_step() {
  local label="$1"
  shift
  echo "[$(timestamp)] ${label}"
  "$@"
}

if ! command -v docker >/dev/null 2>&1; then
  echo "[$(timestamp)] docker command not found, skip"
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  echo "[$(timestamp)] docker daemon unavailable, skip"
  exit 1
fi

echo
echo "========== docker-safe-prune started at $(timestamp) =========="
echo "[before] docker system df"
docker system df
echo

if [ "$PRUNE_STOPPED_CONTAINERS" = "1" ]; then
  run_step \
    "Pruning stopped containers older than ${STOPPED_CONTAINER_UNTIL}" \
    docker container prune -f --filter "until=${STOPPED_CONTAINER_UNTIL}"
  echo
fi

run_step \
  "Pruning dangling images older than ${DANGLING_UNTIL}" \
  docker image prune -f --filter "until=${DANGLING_UNTIL}"
echo

run_step \
  "Pruning unused tagged images older than ${UNUSED_IMAGE_UNTIL}" \
  docker image prune -a -f --filter "until=${UNUSED_IMAGE_UNTIL}"
echo

run_step \
  "Pruning build cache older than ${BUILDER_CACHE_UNTIL}" \
  docker builder prune -f --filter "until=${BUILDER_CACHE_UNTIL}"
echo

if [ "$PRUNE_UNUSED_NETWORKS" = "1" ]; then
  run_step \
    "Pruning unused docker networks" \
    docker network prune -f
  echo
fi

echo "[after] docker system df"
docker system df
echo "========== docker-safe-prune finished at $(timestamp) =========="
echo

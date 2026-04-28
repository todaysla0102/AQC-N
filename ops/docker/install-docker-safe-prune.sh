#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

install -m 0755 "${SCRIPT_DIR}/docker-safe-prune.sh" /usr/local/sbin/docker-safe-prune.sh
install -m 0644 "${SCRIPT_DIR}/../systemd/docker-safe-prune.service" /etc/systemd/system/docker-safe-prune.service
install -m 0644 "${SCRIPT_DIR}/../systemd/docker-safe-prune.timer" /etc/systemd/system/docker-safe-prune.timer
install -m 0644 "${SCRIPT_DIR}/../logrotate/docker-safe-prune" /etc/logrotate.d/docker-safe-prune

if [ ! -f /etc/docker-safe-prune.conf ]; then
  cat >/etc/docker-safe-prune.conf <<'EOF'
# Remove dangling build leftovers after one day.
DANGLING_UNTIL=24h

# Keep unused tagged images for a week in case a recent rollback is needed.
UNUSED_IMAGE_UNTIL=168h

# Clean old build cache after a week.
BUILDER_CACHE_UNTIL=168h

# Clear stopped containers after a week so they no longer pin old images.
STOPPED_CONTAINER_UNTIL=168h
PRUNE_STOPPED_CONTAINERS=1

# Keep unused networks untouched by default.
PRUNE_UNUSED_NETWORKS=0

LOG_FILE=/var/log/docker-safe-prune.log
EOF
  chmod 0644 /etc/docker-safe-prune.conf
fi

systemctl daemon-reload
systemctl enable --now docker-safe-prune.timer

if [ "${1:-}" = "--run-now" ]; then
  systemctl start docker-safe-prune.service
fi

systemctl status docker-safe-prune.timer --no-pager

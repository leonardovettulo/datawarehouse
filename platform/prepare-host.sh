#!/usr/bin/env bash
# Prepare /srv/dw bind-mount dirs on the Ubuntu host. Run once as root before
# the first `docker compose -f platform/compose.prod.yaml up`.
# ClickHouse image user is uid 101; Postgres alpine is uid 999.
# https://clickhouse.com/docs/get-started/setup/self-managed/docker
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

install -d -m 755 \
  /srv/dw/clickhouse \
  /srv/dw/clickhouse-logs \
  /srv/dw/postgres \
  /srv/dw/metabase \
  /srv/dw/archive \
  /srv/dw/backups/clickhouse \
  /srv/dw/backups/pg \
  /srv/dw/platform \
  /srv/dw/orchestration

chown 101:101 /srv/dw/clickhouse /srv/dw/clickhouse-logs /srv/dw/backups/clickhouse
chown 999:999 /srv/dw/postgres

echo "Host directories are ready. From the repo root:"
echo "  docker compose --project-directory platform -f platform/compose.prod.yaml --env-file .env up -d"

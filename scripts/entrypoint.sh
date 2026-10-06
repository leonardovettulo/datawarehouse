#!/usr/bin/env bash
set -euo pipefail

: "${DAGSTER_POSTGRES_HOST:=postgres}"
: "${DAGSTER_POSTGRES_PORT:=5432}"
: "${DAGSTER_POSTGRES_USER:?DAGSTER_POSTGRES_USER is required}"
: "${DAGSTER_POSTGRES_DB:?DAGSTER_POSTGRES_DB is required}"

echo "Waiting for Postgres at ${DAGSTER_POSTGRES_HOST}:${DAGSTER_POSTGRES_PORT}..."
until pg_isready -h "${DAGSTER_POSTGRES_HOST}" -p "${DAGSTER_POSTGRES_PORT}" -U "${DAGSTER_POSTGRES_USER}" -d "${DAGSTER_POSTGRES_DB}" >/dev/null 2>&1; do
  sleep 1
done
echo "Postgres is ready."

echo "Running Dagster instance migrations (no-op if already applied)..."
dagster instance migrate

# Runs execute as children of the daemon (DefaultRunLauncher), so any run still
# marked in progress when the daemon starts died with the previous container.
# Fail them, otherwise max_concurrent_runs: 1 blocks the queue forever.
if [ "${1:-}" = "dagster-daemon" ]; then
  python /opt/dagster/app/dagster_ops.py fail-orphans
fi

exec "$@"

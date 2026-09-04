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

exec "$@"

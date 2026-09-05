#!/bin/bash
set -euo pipefail

if [ "${ENABLE_LOCAL_SOURCE:-}" != "1" ]; then
  echo "Skipping local source seed."
  exit 0
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname source \
    -f /docker-entrypoint-initdb.d/sql/source.sql

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname source <<-EOSQL
    GRANT USAGE ON SCHEMA public TO source_reader;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO source_reader;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO source_reader;
EOSQL

echo "Source database seeded (local stand-in for the SQL Server replica)."

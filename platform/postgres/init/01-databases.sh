#!/bin/bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE USER metabase WITH PASSWORD '${PG_METABASE_PASSWORD}';
    CREATE DATABASE metabase OWNER metabase;

    CREATE USER dagster WITH PASSWORD '${PG_DAGSTER_PASSWORD}';
    CREATE DATABASE dagster OWNER dagster;
EOSQL

if [ "${ENABLE_LOCAL_SOURCE:-}" = "1" ]; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
      CREATE USER source_reader WITH PASSWORD '${PG_SOURCE_PASSWORD}';
      CREATE DATABASE source OWNER ${POSTGRES_USER};
      GRANT CONNECT ON DATABASE source TO source_reader;
EOSQL
  echo "Postgres databases metabase, dagster, and source created."
else
  echo "Postgres databases metabase and dagster created (no local source seed)."
fi

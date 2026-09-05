#!/bin/bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 \
  -v metabase_password="$PG_METABASE_PASSWORD" \
  -v dagster_password="$PG_DAGSTER_PASSWORD" \
  --username "$POSTGRES_USER" --dbname postgres <<-'EOSQL'
    CREATE USER metabase WITH PASSWORD :'metabase_password';
    CREATE DATABASE metabase OWNER metabase;

    CREATE USER dagster WITH PASSWORD :'dagster_password';
    CREATE DATABASE dagster OWNER dagster;
EOSQL

if [ "${ENABLE_LOCAL_SOURCE:-}" = "1" ]; then
  psql -v ON_ERROR_STOP=1 \
    -v source_password="$PG_SOURCE_PASSWORD" \
    -v postgres_owner="$POSTGRES_USER" \
    --username "$POSTGRES_USER" --dbname postgres <<-'EOSQL'
      CREATE USER source_reader WITH PASSWORD :'source_password';
      CREATE DATABASE source OWNER :"postgres_owner";
      GRANT CONNECT ON DATABASE source TO source_reader;
EOSQL
  echo "Postgres databases metabase, dagster, and source created."
else
  echo "Postgres databases metabase and dagster created (no local source seed)."
fi

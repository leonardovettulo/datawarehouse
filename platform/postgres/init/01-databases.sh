#!/bin/bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE USER metabase WITH PASSWORD '${PG_METABASE_PASSWORD}';
    CREATE DATABASE metabase OWNER metabase;

    CREATE USER dagster WITH PASSWORD '${PG_DAGSTER_PASSWORD}';
    CREATE DATABASE dagster OWNER dagster;

    CREATE USER source_reader WITH PASSWORD '${PG_SOURCE_PASSWORD}';
    CREATE DATABASE source OWNER ${POSTGRES_USER};
    GRANT CONNECT ON DATABASE source TO source_reader;
EOSQL

echo "Postgres databases metabase, dagster, and source created."

#!/bin/bash
set -euo pipefail

CH=(clickhouse-client --user "${CLICKHOUSE_USER:-default}" --password "${CLICKHOUSE_PASSWORD}")

"${CH[@]}" --query "CREATE DATABASE IF NOT EXISTS raw"
"${CH[@]}" --query "CREATE DATABASE IF NOT EXISTS marts"

"${CH[@]}" --query "
CREATE TABLE IF NOT EXISTS raw.ingest_state
(
    table_name String,
    watermark DateTime64(6, 'UTC'),
    last_batch_id String,
    last_ingested_at DateTime64(6, 'UTC'),
    rows_inserted UInt64
)
ENGINE = MergeTree
ORDER BY (table_name, last_ingested_at)
"

"${CH[@]}" --query "
CREATE TABLE IF NOT EXISTS raw.source_row_counts
(
    captured_at DateTime64(6, 'UTC'),
    table_name String,
    row_count UInt64
)
ENGINE = MergeTree
ORDER BY (captured_at, table_name)
"

"${CH[@]}" --query "
CREATE SETTINGS PROFILE IF NOT EXISTS metabase_profile
    SETTINGS
        readonly = 2,
        max_execution_time = 30,
        max_memory_usage = 2000000000
"

"${CH[@]}" --query "CREATE USER IF NOT EXISTS dagster IDENTIFIED BY '${CH_DAGSTER_PASSWORD}'"
"${CH[@]}" --query "
CREATE USER IF NOT EXISTS metabase IDENTIFIED BY '${CH_METABASE_PASSWORD}'
    SETTINGS PROFILE metabase_profile
"

"${CH[@]}" --query "GRANT SHOW, SELECT, INSERT, ALTER, CREATE, TRUNCATE ON raw.* TO dagster"
"${CH[@]}" --query "GRANT SHOW, SELECT, INSERT, ALTER, CREATE, DROP, TRUNCATE ON marts.* TO dagster"
"${CH[@]}" --query "GRANT SHOW ON *.* TO dagster"
"${CH[@]}" --query "GRANT SHOW, SELECT ON marts.* TO metabase"
"${CH[@]}" --query "GRANT SHOW ON *.* TO metabase"

echo "ClickHouse databases, users, and grants are in place."

# Phase 4 — Ingestion into `raw`

**Status:** watermark + parquet + MergeTree `local_done`. Hash-and-append and log-shipping retries `not_started`. Tracker: [STATUS.md](../STATUS.md).

Code: `etl/assets/raw.py`.

## Pattern (per table)

1. Read last watermark from `raw.ingest_state`
2. Pull the delta from the source
3. Write Parquet to `/srv/dw/archive/<source>/<table>/<yyyy>/<mm>/<yyyy-mm-dd>_<batch_id>.parquet.zst`
4. Insert into `raw.<table>` with `_ingested_at` (UTC) and `_batch_id`
5. Advance the watermark **only after both writes succeed**

Parquet first. If ClickHouse insert fails, the extract still exists and the batch is replayable.

## Table engines

- MergeTree, `ORDER BY (id, _ingested_at)`, `PARTITION BY toYYYYMM(fecha)`
- No `ReplacingMergeTree` in `raw`
- No `ALTER TABLE ... UPDATE/DELETE` in `raw`

## Still to do (needs relevamiento)

- Confirm restore interval; schedule around log-shipping kills; every asset retry-safe
- Overwrite-in-place tables: hash-and-append, hourly
- Chunked cursors for large tables (seed is tiny; currently one SELECT)
- Historical backfill vs a trusted institution report, signed off

## How to check

```bash
make pipeline
make verify
find is via `make verify` (lists parquet inside the `archive_data` volume).
```

Expected seed counts: `raw.compras` 30, `raw.entregas_farmacia` 50. Re-run should add 0 rows.

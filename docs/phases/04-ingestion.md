# Phase 4 — Ingestion into `raw`

**Status:** watermark + parquet + MergeTree `local_done`. Hash-and-append and log-shipping retries `not_started`. Tracker: [STATUS.md](../STATUS.md).

Code: `etl/assets/raw.py`.

## Pattern (per table)

1. Read last watermark from `raw.ingest_state`
2. Stream the delta from the source in chunks of `EXTRACT_CHUNK_ROWS` (default 50 000, server-side cursor)
3. Per chunk: append to Parquet `/srv/dw/archive/<source>/<table>/<yyyy>/<mm>/<yyyy-mm-dd>_<batch_id>.parquet.zst`, then insert into `raw.<table>` with `_ingested_at` (UTC) and `_batch_id`
4. Advance the watermark **only after every chunk landed**
5. Asset check `matches_source` (blocking): every source row up to the watermark has its `id` in raw. Missing rows fail the run before marts are rebuilt; ids deleted at the source only warn.

Parquet first. If a run dies half-way, the next run re-reads the same delta; marts
read the latest version per `id`, so repeated rows never count twice. Memory use is
bounded by the chunk size, not the table size.

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

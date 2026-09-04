# Phase 5 — Backups

**Status:** `not_started` (backup disk is declared; jobs are not). Tracker: [STATUS.md](../STATUS.md).

Do this the same week `raw` starts capturing overwritten state. Unbacked-up overwritten state is permanent data loss.

## Intended jobs (systemd timers on the host, not containers)

1. `pg_dump` of `metabase` and `dagster`, zstd
2. ClickHouse `BACKUP DATABASE raw` incremental against a weekly full (`Disk('backups', ...)`)
3. `age` encrypt, `rclone` off-box; `rclone sync` of the Parquet archive

ClickHouse already has a `backups` disk in `platform/clickhouse/config.d/backups.xml` mounted at volume `clickhouse_backups`.

## Two layers

| | Parquet archive | ClickHouse `BACKUP` |
|---|---|---|
| Purpose | never lose history (RPO) | restore fast (RTO) |
| Restore | replay through the loader | direct |
| Covers | CH lost, corruption, bad transform found months later | disk failure, need it today |

## Non-negotiables

1. Off-box. Same disk is not a backup.
2. Encrypted before it leaves (health data; NAS may be weaker).
3. `MB_ENCRYPTION_SECRET_KEY` stored separately from dumps.
4. Config in git (both compose projects, `config.d`, `users.d`, `dagster.yaml`, nginx, backup scripts).
5. Retention 7 daily / 4 weekly / 6 monthly until legal answers.

## Restore drill (do once now, again week 12)

- Restore Metabase dump into scratch Postgres, point a throwaway Metabase at it, confirm a dashboard renders
- Restore one ClickHouse partition into a scratch database, compare counts
- Replay one day of Parquet into a scratch table, compare against `raw`
- Write down elapsed time — that is the RTO

## How to check

Not scripted yet. When jobs exist: last-night stamp in `data/backups/` plus a documented restore timing.

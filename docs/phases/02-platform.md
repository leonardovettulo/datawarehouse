# Phase 2 — Platform stack

**Status:** `local_done`. Prod: `not_started`. Tracker: [STATUS.md](../STATUS.md).

Stateful services, started once, left alone. File: `platform/compose.yaml`.

Local: merged with the orchestration compose into project `dw-local` (`make up`). Production: own project `dw-platform` on `dw_net`.

## Services

| Service | Image | Local port |
|---|---|---|
| `postgres` | `postgres:16-alpine` | unpublished |
| `clickhouse` | `clickhouse/clickhouse-server:24.8` | `127.0.0.1:8123` |
| `metabase` | `metabase/metabase:v0.63.16.x` | `127.0.0.1:3000` |

Metabase 0.54+ bundles the ClickHouse driver. The plan's `v0.50.x` + extra JAR is not used.

## Secrets

`.env` mode `600`, not in git. `.env.example` is committed.

`MB_ENCRYPTION_SECRET_KEY` must also live in the institution password manager. Without it, a Metabase `pg_dump` restores into an unusable instance.

## Postgres

Init: `platform/postgres/init/01-databases.sh` creates `metabase` and `dagster` with separate owners. Local also creates `source` (SQL Server stand-in) and seeds it (`02-source.sh`).

## ClickHouse

- `config.d/memory.xml` — 50% RAM ratio, 20 concurrent queries
- `config.d/backups.xml` — `backups` disk at `/backups`
- Init: databases `raw` / `marts`, users `dagster` / `metabase`, profile `readonly=2` (reads only, settings allowed for JDBC) + 30s + 2 GB for Metabase
- `default` has a password (`CH_ADMIN_PASSWORD`); it is not passwordless

Init scripts run only when the data directory is empty.

## Metabase

Appdb = Postgres `metabase`. First-time admin + ClickHouse connection: `make setup-metabase` (idempotent).

## How to check

```bash
make wait
make setup-metabase
# Metabase UI → Browse → ClickHouse marts
```

`SELECT 1` against a dummy table is covered after `make pipeline` by browsing `marts.indicador_cobertura`.

# Implementation status

Single tracker for the on-prem DW plan. Update the **Local** / **Prod** columns as work lands. Do not mark prod done from a local check.

Legend:

| Status | Meaning |
|---|---|
| `not_started` | Not touched |
| `in_progress` | Being built |
| `local_done` | Works on this laptop against the seeded source |
| `n/a_local` | Does not apply to local (needs the institution) |
| `blocked` | Waiting on someone else; see notes |
| `prod_done` | Done on the Ubuntu server |

---

## Phase 0 — Prerequisites (institution)

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 0.1 | Server provisioned, sudo | `n/a_local` | `not_started` | |
| 0.2 | SQL Server replica readable, restore interval known | `n/a_local` | `not_started` | Local uses Postgres `source` |
| 0.3 | Read-only SQL Server login | `n/a_local` | `not_started` | |
| 0.4 | Static IP + DNS | `n/a_local` | `not_started` | Local: localhost |
| 0.5 | Internal CA cert | `n/a_local` | `not_started` | Local: HTTP |
| 0.6 | LAN subnets for Metabase | `n/a_local` | `not_started` | |
| 0.7 | Backup destination (NAS / second host) | `n/a_local` | `not_started` | |
| 0.8 | Confidentiality / DPA / access approvals | `n/a_local` | `not_started` | Ley 25.326 |
| 0.9 | Decision: patient identifiers on the tablero? | `n/a_local` | `not_started` | Local hashes `nro_historia` at marts |
| 0.10 | Governance one-pager | `n/a_local` | `not_started` | Week 2 deliverable |
| 0.11 | Table inventory spreadsheet | `in_progress` | `not_started` | Seeded 4 tables; real relevamiento still needed |

## Phase 1 — Host baseline

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 1.1 | Disk layout `/srv/dw` | `n/a_local` | `not_started` | `platform/prepare-host.sh` (chown 101:101 / 999:999) |
| 1.2 | Timezone + chrony, timestamps UTC in CH | `local_done` | `not_started` | |
| 1.3 | SSH hardened | `n/a_local` | `not_started` | |
| 1.4 | Docker CE + log rotation | `n/a_local` | `not_started` | Engine ≥ 20.10.10; CH logger.xml + clickhouse-logs |
| 1.5 | UFW, no non-loopback publishes | `local_done` | `not_started` | Local binds are `127.0.0.1` |
| 1.6 | nginx + TLS placeholder | `not_started` | `not_started` | Local Metabase is :3000 |

## Phase 2 — Platform stack

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 2.1 | `dw_net` + two compose files | `local_done` | `not_started` | Merged as project `dw-local` |
| 2.2 | Secrets in `.env` (not git), `.env.example` committed | `local_done` | `not_started` | |
| 2.3 | `MB_ENCRYPTION_SECRET_KEY` also off-box | `n/a_local` | `not_started` | |
| 2.4 | Postgres: dbs `metabase`, `dagster` (+ local `source`) | `local_done` | `not_started` | |
| 2.5 | ClickHouse 24.8, memory cap, backup disk, log rotation | `local_done` | `not_started` | `compose.prod.yaml` + `CH_MEM_LIMIT` on the box |
| 2.6 | Users `dagster` (write raw+marts), `metabase` (read marts) | `local_done` | `not_started` | |
| 2.7 | Metabase on 127.0.0.1:3000, appdb Postgres | `local_done` | `not_started` | Image `v0.63.16.x` (driver bundled) |
| 2.8 | Metabase connected to ClickHouse, `SELECT` on marts | `local_done` | `not_started` | `make setup-metabase` |
| 2.9 | Prod platform compose (no CH ports, bind mounts, no fake source) | `n/a_local` | `not_started` | `platform/compose.prod.yaml` |

## Phase 3 — Orchestration stack

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 3.1 | Dagster webserver `127.0.0.1:3030` + daemon | `local_done` | `not_started` | |
| 3.2 | `etl/` bind-mounted, reload without rebuild | `not_started` | `not_started` | Local: copied into image (`make up-build`). Bind-mounts blocked by Docker Desktop file sharing. |
| 3.3 | Trivial asset: source row counts → ClickHouse | `local_done` | `not_started` | `source_row_counts` |
| 3.4 | pymssql / SQL Server driver | `not_started` | `not_started` | Local uses `psycopg` |
| 3.5 | Daemon `mem_limit` | `not_started` | `not_started` | Add when RAM is known |

## Phase 4 — Ingestion into `raw`

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 4.1 | Watermark in `raw.ingest_state` | `local_done` | `not_started` | |
| 4.2 | Parquet first, then CH, then advance watermark | `local_done` | `not_started` | volume `archive_data` |
| 4.3 | Chunked reads | `in_progress` | `not_started` | Seed is tiny; pattern is one SELECT |
| 4.4 | Retry-safe around log-shipping kills | `not_started` | `not_started` | |
| 4.5 | Hash-and-append for overwrite-in-place tables | `not_started` | `not_started` | Needs relevamiento |
| 4.6 | MergeTree, monthly partitions, no ReplacingMergeTree in raw | `local_done` | `not_started` | |
| 4.7 | Historical backfill + signed reconciliation | `n/a_local` | `not_started` | Local seed is the backfill |

## Phase 5 — Backups

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 5.1 | Nightly pg_dump + CH BACKUP + off-box rclone | `not_started` | `not_started` | Disk declared; jobs not yet |
| 5.2 | Encrypted before leaving the box (`age`) | `not_started` | `not_started` | |
| 5.3 | Restore drill with timings | `not_started` | `not_started` | |
| 5.4 | Retention 7/4/6 pending legal | `not_started` | `not_started` | |

## Phase 6 — Modeling

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 6.1 | `marts.insumo_evento` | `local_done` | `not_started` | |
| 6.2 | `marts.trazabilidad_gap` with `motivo` | `local_done` | `not_started` | |
| 6.3 | `marts.indicador_*` with written definition | `local_done` | `not_started` | `indicador_cobertura` |
| 6.4 | Rebuildable from raw, partition replace | `local_done` | `not_started` | Local: TRUNCATE + INSERT |
| 6.5 | Pseudonymize patient ids at marts boundary | `local_done` | `not_started` | SHA256 + pepper; confirm with Consejo |

## Phase 7 — Metabase, access, dashboards

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 7.1 | Groups per area, collection permissions | `not_started` | `not_started` | |
| 7.2 | LDAP/AD | `n/a_local` | `not_started` | |
| 7.3 | Only `marts` exposed | `local_done` | `not_started` | CH grants |
| 7.4 | Metabase models over marts | `not_started` | `not_started` | Browse tables works after bootstrap |
| 7.5 | Native query off for general users | `not_started` | `not_started` | |

## Phase 8 — Operations and handover

| ID | Item | Local | Prod | Notes |
|---|---|---|---|---|
| 8.1 | Disk > 80% alert | `not_started` | `not_started` | |
| 8.2 | Dagster failure email | `not_started` | `not_started` | |
| 8.3 | Log-shipping lag alert | `n/a_local` | `not_started` | |
| 8.4 | Backup-job-missed alert | `not_started` | `not_started` | |
| 8.5 | Runbook in git | `in_progress` | `not_started` | `docs/local.md` is the local runbook |

---

## How to check this locally

```bash
make verify          # counts + parquet + Metabase connection
```

When a row moves from `not_started` to `local_done`, say so in the same PR/commit as the code.

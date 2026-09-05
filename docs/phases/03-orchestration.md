# Phase 3 — Orchestration stack

**Status:** local stack and production Compose done; SQL Server driver remains
`not_started` while the pipelines are mocks. Tracker: [STATUS.md](../STATUS.md).

Local: `compose.yaml`. Production: root `compose.prod.yaml`, project
`dw-orchestration`, attached to the platform's external `dw_net`.

## Services

Same image, two processes:

- `dagster-webserver` → `127.0.0.1:3030`
- `dagster-daemon` — schedules + queued run execution (runs execute **inside** this container)

The local image copies `etl/`; code changes require `make up-build`.
`workspace.yaml` loads `python_module: etl.definitions`.

## Deploy loop

```bash
# local: code or dependencies changed
make up-build
make pipeline

# production (platform must be up first)
docker compose -f compose.prod.yaml --env-file .env up -d --build
```

Never restart while the nightly job is running.

## Driver

Local: `psycopg` against Postgres `source`. The production Compose defines
`SOURCE_SQLSERVER_*`, encryption, and certificate-validation settings. The
current mock resource still uses `psycopg`; implement the SQL Server adapter
before running real pipelines. Start with `pymssql`, moving to `pyodbc` +
`msodbcsql18` only if needed.

Complete runs are serialized (`max_concurrent_runs: 1`) until ingestion and
mart replacement become concurrency-safe. The production defaults are 1 GB for
the webserver and 4 GB for the daemon; adjust them to the host RAM.

## Deliverable

Asset `source_row_counts` reads counts from the source and writes `raw.source_row_counts`. Included in `make pipeline`. Schedule `nightly_ingest` at 06:00 America/Argentina/Cordoba.

## How to check

```bash
make pipeline
# Dagster UI http://127.0.0.1:3030 → job ingest_and_marts green
```

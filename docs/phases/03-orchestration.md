# Phase 3 — Orchestration stack

**Status:** `local_done` except SQL Server driver and daemon mem_limit. Tracker: [STATUS.md](../STATUS.md).

File: `compose.yaml`. Production: own git repo / project `dw-orchestration`.

## Services

Same image, two processes:

- `dagster-webserver` → `127.0.0.1:3030`
- `dagster-daemon` — schedules + queued run execution (runs execute **inside** this container)

`etl/` is bind-mounted. `workspace.yaml` loads `python_module: etl.definitions`.

## Deploy loop

```bash
# local
# edit etl/** → Reload code location in the UI
# schedules/sensors changed → restart dagster-daemon
# requirements changed → make up-build
```

Never restart while the nightly job is running.

## Driver

Local: `psycopg` against Postgres `source`. Production: start with `pymssql`. Move to `pyodbc` + `msodbcsql18` only if bulk reads stall (adds a Microsoft apt repo and EULA to the Dockerfile).

## Deliverable

Asset `source_row_counts` reads counts from the source and writes `raw.source_row_counts`. Included in `make pipeline`. Schedule `nightly_ingest` at 06:00 America/Argentina/Cordoba.

## How to check

```bash
make pipeline
# Dagster UI http://127.0.0.1:3030 → job ingest_and_marts green
```

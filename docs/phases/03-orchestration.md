# Phase 3 — Orchestration stack

**Status:** local stack and production Compose done; SQL Server driver remains
`not_started` while the pipelines are mocks. Tracker: [STATUS.md](../STATUS.md).

Local: `compose.yaml`. Production: root `compose.prod.yaml`, project
`dw-orchestration`, attached to the platform's external `dw_net`.

## Services

Same image, two processes:

- `dagster-webserver` → `127.0.0.1:3030`
- `dagster-daemon` — schedules + queued run execution (runs execute **inside** this container)

The image copies `etl/`, so new code means a new image and a restart of both
processes. `workspace.yaml` loads `python_module: etl.definitions`.

## Deploy loop

```bash
# local: code or dependencies changed
make deploy
make pipeline

# production (platform must be up first)
git pull
scripts/deploy.sh prod
```

`scripts/deploy.sh`:

1. Builds the new image while the old one keeps running.
2. Runs `dagster definitions validate` in the new image; aborts if it fails.
3. Waits until no run is in progress (`DEPLOY_WAIT_TIMEOUT`, default 1800 s).
   On timeout it aborts and restarts nothing.
4. Recreates `dagster-webserver` and `dagster-daemon` only. Queued runs survive
   in Postgres and start afterwards.

### Orphaned runs

Runs execute as children of the daemon, so a daemon restart (reboot, OOM kill,
`docker restart`) kills them while Postgres still says `STARTED`. With
`max_concurrent_runs: 1` that would block the queue forever. The entrypoint runs
`dagster_ops.py fail-orphans` before starting the daemon, marking those runs as
failed. `run_monitoring.max_runtime_seconds` (6 h) in `dagster/dagster.yaml`
fails runs that hang with a live process. Re-run a failed run from the UI.

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

# On-prem data warehouse

Local ClickHouse warehouse, Dagster orchestration, Metabase serving. The source is a seeded Postgres database that stands in for the SQL Server read-only replica.

## Quick start

```bash
cp .env.example .env          # already done if you just cloned this tree
make bootstrap                # build, start, ingest, set up Metabase, verify
```

Then open:

| Surface | URL | Notes |
|---|---|---|
| Metabase | http://127.0.0.1:3000 | `admin@localhost.local` / `LocalDev123456` |
| Dagster | http://127.0.0.1:3030 | No auth; local only |
| ClickHouse HTTP | http://127.0.0.1:8123 | User `default`, password from `.env` |

Day to day after the first bootstrap:

```bash
make up                       # start without rebuilding
make pipeline                 # queue extracts + marts and wait (no-op if no new source rows)
make deploy                   # ship etl/ changes; waits for running jobs before restarting
make verify
make test                     # e2e tests on a throwaway stack; never touches dw-local
make down
```

If you change dependencies: run `uv lock`, commit `uv.lock`, then
`make deploy`. Docker builds use `uv sync --frozen`.

If you change only Python under `etl/`: `make deploy` (code is copied into the image;
the script waits for any running job before restarting Dagster). Production:
`scripts/deploy.sh prod`.

Wipe everything local and start again: `make reset && make bootstrap`.

## What runs

```
SQL Server replica (prod)     Postgres `source` (local stand-in)
        │                                │
        └──────────── extract ───────────┘
                         │
              parquet volume archive_data
                         │
                   ClickHouse `raw`
                         │
                   ClickHouse `marts`
                         │
                      Metabase
```

Local uses two merged Compose files in one project (`dw-local`):

- `platform/compose.yaml` — Postgres, ClickHouse, Metabase (stateful, rarely rebuilt)
- `compose.yaml` — Dagster webserver + daemon (redeployed often)

`make up` merges them. Production uses `platform/compose.prod.yaml` and the
root `compose.prod.yaml` as separate projects on external `dw_net`; see
`docs/phases/02-platform.md`.

## Implementation tracker

Work is tracked with status in **[docs/STATUS.md](docs/STATUS.md)**. Phase write-ups:

- [Local runbook](docs/local.md)
- [Phase 0 — Prerequisites](docs/phases/00-prerequisites.md)
- [Phase 1 — Host baseline](docs/phases/01-host-baseline.md)
- [Phase 2 — Platform](docs/phases/02-platform.md)
- [Phase 3 — Orchestration](docs/phases/03-orchestration.md)
- [Phase 4 — Ingestion](docs/phases/04-ingestion.md)
- [Phase 5 — Backups](docs/phases/05-backups.md)
- [Phase 6 — Modeling](docs/phases/06-modeling.md)
- [Phase 7 — Metabase](docs/phases/07-metabase.md)
- [Phase 8 — Operations](docs/phases/08-operations.md)
- [Database secret rotation](docs/secret-rotation.md)
- [Open questions](docs/open-questions.md)

## Layout

```
platform/                   # compose + init for postgres / clickhouse / metabase
compose.prod.yaml           # production Dagster stack on external dw_net
uv.lock                     # exact Python dependency graph used by Docker
etl/                        # Dagster assets (copied into the image locally)
  assets/raw.py             # watermark extract → parquet → raw.*
  assets/marts.py           # rebuild marts from raw
  resources.py
  definitions.py
scripts/                    # wait, setup-metabase, verify, container entrypoint
docs/                       # phase docs + STATUS.md
data/                       # unused locally; production bind-mounts live under /srv/dw
```

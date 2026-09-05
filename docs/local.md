# Local runbook

This is the working path on a laptop. Production host steps live in the phase docs and stay `not_started` until the Ubuntu box exists.

## One-shot

```bash
cp .env.example .env    # local passwords; never use these in production
make bootstrap
```

`bootstrap` = build images → start compose → wait until healthy → materialize all assets → set up Metabase → `make verify`.

## URLs and users

| What | Where | Credentials |
|---|---|---|
| Metabase | http://127.0.0.1:3000 | `MB_ADMIN_EMAIL` / `MB_ADMIN_PASSWORD` in `.env` |
| Dagster | http://127.0.0.1:3030 | none |
| ClickHouse HTTP | http://127.0.0.1:8123 | `default` / `CH_ADMIN_PASSWORD` |

ClickHouse users inside the network:

- `dagster` — write `raw` and `marts`
- `metabase` — read `marts` only, `readonly=2`, 30s query cap

## What the first pipeline does

1. Reads four tables from Postgres database `source` (seeded at first Postgres start).
2. Writes zstd Parquet under `/srv/dw/archive/source/<table>/<yyyy>/<mm>/` (volume `archive_data`).
3. Inserts into ClickHouse `raw.*` with `_ingested_at` (UTC) and `_batch_id`.
4. Advances `raw.ingest_state` only after both writes succeed.
5. Rebuilds `marts.insumo_evento`, `marts.trazabilidad_gap`, `marts.indicador_cobertura`.
6. Hashes `nro_historia` at the marts boundary (`PSEUDONYM_PEPPER`).

Re-running `make pipeline` after a successful run inserts 0 raw rows (watermark has caught up) and still rebuilds marts.

## Deploy loop (local)

| Change | Action |
|---|---|
| Python under `etl/` | `make up-build` (image copy; no bind-mount on this Docker Desktop) |
| `pyproject.toml` / Dockerfile | `make up-build` |
| ClickHouse `config.d` or Postgres init | Init scripts run **only on an empty data dir**. `make reset && make bootstrap` |
| `.env` secrets | `make down && make up` |
| Prod host dirs | `sudo ./platform/prepare-host.sh` then `compose.prod.yaml` |

Do not `git pull` + restart while a run is in progress.

## Useful commands

```bash
make logs              # everything
make logs-platform     # postgres, clickhouse, metabase
make logs-orch         # dagster
make pipeline          # materialize '*'
make verify
make reset             # docker compose down -v
```

ClickHouse ad-hoc:

```bash
docker compose -f platform/compose.yaml -f compose.yaml --project-directory . \
  exec clickhouse clickhouse-client --user default --password local-ch-admin
```

```sql
SELECT table_name, row_count FROM raw.source_row_counts ORDER BY captured_at DESC LIMIT 10;
SELECT stage, count() FROM marts.insumo_evento GROUP BY stage;
SELECT insumo_codigo, motivo, qty_entrega, qty_hc FROM marts.trazabilidad_gap;
```

## Ports (loopback only)

| Port | Service |
|---|---|
| 3000 | Metabase |
| 3030 | Dagster |
| 8123 | ClickHouse HTTP (debug) |

Postgres is not published. Dagster is not behind nginx locally.

## When something is already half-up

Named volumes persist across `make down`. Postgres init (including the seed) runs only once, when the volume is empty. If the seed is missing, `make reset && make bootstrap`.

# dagsteross

Single-box [Dagster OSS](https://docs.dagster.io/) deployment: Postgres + webserver + daemon, one Docker image, in-process code loading. No gRPC code servers, no Docker-in-Docker run launcher.

## What's in the box

| Service | Role |
|---------|------|
| `postgres` | Run, schedule, and event log storage |
| `dagster-webserver` | UI at port 3000 |
| `dagster-daemon` | Schedules, sensors, queued run execution |

Pipeline code lives in `my_pipelines/definitions.py` and is loaded via `workspace.yaml`:

```yaml
load_from:
  - python_module: my_pipelines.definitions
```

Both webserver and daemon import the module in-process. Deploying new code means rebuilding the image and restarting those two containers.

## Quick start (local)

```bash
cp .env.example .env          # edit POSTGRES_PASSWORD if you like
make up                       # build + start
open http://localhost:3000    # Dagster UI
```

Smoke test:

```bash
make test-local
```

Stop:

```bash
make down
```

## Server deploy

Same compose file works on a VPS. Typical flow:

1. Clone this repo on the server.
2. Set strong values in `.env` (especially `POSTGRES_PASSWORD`).
3. `docker compose up -d --build`
4. Put nginx or Caddy in front with basic auth or OAuth — Dagster OSS has no built-in auth.

To ship new pipeline code:

```bash
git pull
docker compose up -d --build dagster-webserver dagster-daemon
```

## Configuration

**`dagster/dagster.yaml`** — instance config mounted at `DAGSTER_HOME`:

- Postgres storage (env-var credentials)
- `QueuedRunCoordinator` with `max_concurrent_runs: 2` — caps subprocess runs on the host
- Default run launcher (no separate container per run)
- Schedule/sensor tick retention (30 / 7 days)
- Telemetry off

**`.env`** — Postgres credentials and UI port.

## Adding dependencies

Edit `pyproject.toml`, rebuild:

```bash
docker compose build
docker compose up -d
```

Pre-installed: `dagster`, `dagster-dbt`, `dlt`, `clickhouse-connect`.

## Local dev without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
export DAGSTER_HOME=$(pwd)/dagster   # uses local dagster.yaml; needs a Postgres reachable at hostname `postgres` or edit dagster.yaml
dagster dev -m my_pipelines.definitions
```

For pure local iteration, point `dagster/dagster.yaml` storage at a local Postgres or use Dagster's default SQLite by temporarily removing the postgres block.

## Operations notes

| Topic | Behavior |
|-------|----------|
| Hot reload | None — restart webserver + daemon after code changes |
| Daemon health | `restart: unless-stopped` + `dagster-daemon liveness-check` |
| Run history | Not auto-purged in OSS; plan periodic cleanup if volume grows |
| Upgrades | After bumping Dagster in `pyproject.toml`, run `make migrate` before or during rollout |
| Auth | Add a reverse proxy; not included here |

## Project layout

```
.
├── dagster/dagster.yaml    # instance config
├── my_pipelines/           # your code (edit definitions.py)
├── workspace.yaml          # in-process module loader
├── Dockerfile              # single image for webserver + daemon
├── docker-compose.yml
├── scripts/entrypoint.sh   # wait for Postgres, run migrations
└── pyproject.toml
```

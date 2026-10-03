# Phase 8 — Operations and handover

**Status:** alerts `local_done` (tested against a fake heartbeat receiver); not deployed. Tracker: [STATUS.md](../STATUS.md).

## Alerting

Everything reports to Better Stack heartbeats; Better Stack does the routing
(email, SMS, app). Each signal catches something the others can't:

| Signal | Code | Fires when | Catches |
|---|---|---|---|
| Host heartbeat | `platform/monitoring/dw-healthcheck.sh` (systemd timer, 5 min) | `/fail` on disk ≥ 80%, memory < 10% available, an expected container missing / stopped / unhealthy. No ping at all when the box or Docker is down | Server-level problems, including total outage |
| Pipeline heartbeat | `etl/alerts.py` `heartbeat_on_success` / `alert_on_run_failure` | Ping on every successful `ingest_and_marts`; `/fail` with the error and a link to the run on any failed run | Failed runs immediately, and "the nightly did not succeed" including "it never started" (schedule off, daemon dead, queue stuck) |

Nothing but host facts, job names, run ids and error messages leaves the box. No
logs, no rows: patient data never reaches the monitoring service (Ley 25.326).

### Heartbeat service: Better Stack

Heartbeats only need **outbound** HTTPS from the server; nothing inside the LAN is
exposed. Better Stack (Uptime → Heartbeats) and Healthchecks.io both accept
`POST <url>` and `POST <url>/fail`. If the server has no outbound internet,
self-host Healthchecks on a *different* machine — a monitor on the same box can't
report that the box is down.

Set up two heartbeats:

| Heartbeat | Period | Grace | Variable |
|---|---|---|---|
| `dw-host` | 5 min | 5 min | `HOST_HEARTBEAT_URL` in `/etc/dw/healthcheck.env` |
| `dw-nightly` | 24 h | 3 h (the nightly starts 06:00) | `PIPELINE_HEARTBEAT_URL` in `.env` |

Route both to the people in open question 12 (email, SMS or app).

### Install (production)

`sudo ./platform/prepare-host.sh` installs `/usr/local/bin/dw-healthcheck`, the
systemd timer, and `/etc/dw/healthcheck.env` (mode 600; edit `HOST_HEARTBEAT_URL`).

```bash
sudo dw-healthcheck                        # run once by hand; prints the report
systemctl list-timers dw-healthcheck.timer
journalctl -u dw-healthcheck -n 20
```

Pipeline alerts: set `PIPELINE_HEARTBEAT_URL` and `DAGSTER_BASE_URL` in `.env`,
then `scripts/deploy.sh prod`. Empty `PIPELINE_HEARTBEAT_URL` disables them (the
sensors log a warning).

### Local

Put a test heartbeat URL in `PIPELINE_HEARTBEAT_URL` in `.env`, `make deploy`, then
`make pipeline` (success ping). To see a `/fail`, stop ClickHouse and run it again:

```bash
docker compose -p dw-local -f platform/compose.yaml -f compose.yaml --project-directory . stop clickhouse
make pipeline        # fails → /fail reaches Better Stack within ~30 s
docker compose -p dw-local -f platform/compose.yaml -f compose.yaml --project-directory . start clickhouse
```

Still to add: backup-missed heartbeat once backups exist (5.1), log-shipping lag (8.3).

## Runbook (keep in git)

Already started:

- Local deploy / restart / URLs: [../local.md](../local.md)
- Restore: [05-backups.md](05-backups.md) (drill not yet run)
- Who holds encryption keys: `.env` locally; production must be the institution password manager

Still to write: disk-full procedure, prod nginx restart, who to call.

## How to check

No alert bus yet. Local health: `make wait && make verify`.

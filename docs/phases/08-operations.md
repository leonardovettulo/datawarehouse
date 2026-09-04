# Phase 8 — Operations and handover

**Status:** `in_progress` locally (this runbook + STATUS). Alerts `not_started`. Tracker: [STATUS.md](../STATUS.md).

## Minimum viable alerts (production)

- Disk usage over 80% (takes down CH + Postgres + Metabase together)
- Dagster run failure → email via a failure sensor with SMTP
- Log-shipping lag on the replica
- Backup job did not complete last night

## Runbook (keep in git)

Already started:

- Local deploy / restart / URLs: [../local.md](../local.md)
- Restore: [05-backups.md](05-backups.md) (drill not yet run)
- Who holds encryption keys: `.env` locally; production must be the institution password manager

Still to write: disk-full procedure, prod nginx restart, who to call.

## How to check

No alert bus yet. Local health: `make wait && make verify`.

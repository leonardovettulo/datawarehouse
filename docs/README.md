# Docs index

Status lives in [STATUS.md](STATUS.md). How to run the laptop stack: [local.md](local.md).

| Doc | Phase |
|---|---|
| [phases/00-prerequisites.md](phases/00-prerequisites.md) | 0 Institution blockers + relevamiento |
| [phases/01-host-baseline.md](phases/01-host-baseline.md) | 1 Ubuntu disk, Docker, UFW, nginx |
| [phases/02-platform.md](phases/02-platform.md) | 2 ClickHouse, Postgres, Metabase |
| [phases/03-orchestration.md](phases/03-orchestration.md) | 3 Dagster |
| [phases/04-ingestion.md](phases/04-ingestion.md) | 4 `raw` extracts |
| [phases/05-backups.md](phases/05-backups.md) | 5 Backups and restore drill |
| [phases/06-modeling.md](phases/06-modeling.md) | 6 Marts / traceability |
| [phases/07-metabase.md](phases/07-metabase.md) | 7 Access and dashboards |
| [phases/08-operations.md](phases/08-operations.md) | 8 Alerts and handover |
| [secret-rotation.md](secret-rotation.md) | Rotate existing DB credentials safely |
| [open-questions.md](open-questions.md) | Blocking questions from the plan |

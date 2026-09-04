# Phase 0 — Prerequisites

**Status:** `n/a_local` for institution items; table inventory `in_progress` (seeded stand-in only). Prod: `not_started`. Tracker: [STATUS.md](../STATUS.md).

These block production. Chase in week 1; they are the schedule's critical path.

## Institution checklist

Copy this to the Consejo/IT thread. Tick when you have a written answer, not a verbal one.

- [ ] Server provisioned, you have sudo
- [ ] Read-only replica confirmed readable; log restore interval written down
- [ ] SQL Server login, read-only, scoped to the schemas in scope
- [ ] Static IP + DNS name for the DW server
- [ ] Internal CA cert, or written approval to use self-signed
- [ ] LAN subnet(s) allowed to reach Metabase
- [ ] Backup destination: NAS path + credentials, or a second host
- [ ] Confidentiality agreement / DPA signed; access approvals documented (Ley 25.326)
- [ ] Decision: does the tablero need patient identifiers at all?

**Week 2 deliverable:** one page — what data leaves the source, who can see it, where backups live, how long they are kept.

## Source relevamiento (weeks 1–2)

For every table in scope:

| Field | Why |
|---|---|
| Primary key, and whether it is stable | Dedup / hash-and-append |
| Watermark column (`fecha_modificacion`, `rowversion`, monotonic id) | Incremental. No watermark → full snapshot |
| Columns overwritten in place vs append-only | **Most important output.** Overwrites (stock, estados, asignaciones) are lost forever if not snapshotted |
| Row count and average row size | Disk + RAM |
| Soft-delete flag, or hard deletes | |

Local stand-in (not a substitute for the spreadsheet): `platform/postgres/init/sql/source.sql` — `compras`, `entregas_farmacia`, `hc_registros`, `facturacion`. All have integer PKs and `updated_at` watermarks. They are append-only in the seed.

## How to check

Local: `make verify` after bootstrap. Prod: this phase is a paper checklist, not a script.

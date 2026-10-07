# Phase 6 — Modeling

**Status:** `local_done` for the three marts on seeded data. Tracker: [STATUS.md](../STATUS.md).

Code: `etl/assets/marts.py`. Rebuild: each mart is built into `marts.<name>__new`
from the DDL in code, then swapped in with `EXCHANGE TABLES` (atomic). Metabase
never sees an empty or half-built mart; a failed rebuild leaves the previous one.
A DDL change in `marts.py` applies on the next run.

`raw` keeps every extracted version of a row; marts read only the latest version
per `id` (`ORDER BY updated_at DESC, _ingested_at DESC LIMIT 1 BY id`).

## Tables

| Table | Role |
|---|---|
| `marts.insumo_evento` | One row per event, `stage` in `{compra, entrega_farmacia, hc, facturacion}` |
| `marts.trazabilidad_gap` | Per insumo and month, quantities + deltas, `motivo` |
| `marts.indicador_cobertura` | `cobertura_hc` and `cobertura_facturacion` with a written `definicion` |

`motivo` values: `completo`, `no_registrado_hc`, `no_registrado_facturacion`, `no_registrado_hc_ni_facturacion`, `discrepancia`, `sin_entrega`.

The seed is deliberately partial on HC and facturación so the first dashboard shows gaps, not accusations.

## Pseudonymization

Off by default (`PSEUDONYMIZE=0`): `marts.insumo_evento.paciente_ref` is `nro_historia` as stored in `raw`. Set `PSEUDONYMIZE=1` and `PSEUDONYM_PEPPER` to store SHA256(chart number + pepper) instead. With the flag on, a missing pepper fails the mart build rather than hashing with an empty key.

## How to check

```sql
SELECT stage, count() FROM marts.insumo_evento GROUP BY stage;
SELECT motivo, count() FROM marts.trazabilidad_gap GROUP BY motivo;
SELECT indicador, periodo, valor, definicion FROM marts.indicador_cobertura;
```

Every mart must be rebuildable from `raw` with `make pipeline`.

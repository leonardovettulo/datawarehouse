# Phase 6 — Modeling

**Status:** `local_done` for the three marts on seeded data. Tracker: [STATUS.md](../STATUS.md).

Code: `etl/assets/marts.py`. Rebuild: TRUNCATE + INSERT (partition exchange comes later).

## Tables

| Table | Role |
|---|---|
| `marts.insumo_evento` | One row per event, `stage` in `{compra, entrega_farmacia, hc, facturacion}` |
| `marts.trazabilidad_gap` | Per insumo and month, quantities + deltas, `motivo` |
| `marts.indicador_cobertura` | `cobertura_hc` and `cobertura_facturacion` with a written `definicion` |

`motivo` values: `completo`, `no_registrado_hc`, `no_registrado_facturacion`, `no_registrado_hc_ni_facturacion`, `discrepancia`, `sin_entrega`.

The seed is deliberately partial on HC and facturación so the first dashboard shows gaps, not accusations.

## Pseudonymization

`nro_historia` is hashed with SHA256 + `PSEUDONYM_PEPPER` at the raw → marts boundary. Confirm with the Consejo before production. If the tablero does not need identity, Metabase then sits outside the sensitive-data perimeter.

## How to check

```sql
SELECT stage, count() FROM marts.insumo_evento GROUP BY stage;
SELECT motivo, count() FROM marts.trazabilidad_gap GROUP BY motivo;
SELECT indicador, periodo, valor, definicion FROM marts.indicador_cobertura;
```

Every mart must be rebuildable from `raw` with `make pipeline`.

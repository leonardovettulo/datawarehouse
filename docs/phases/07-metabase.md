# Phase 7 — Metabase, access, dashboards

**Status:** connection to `marts` `local_done`. Groups, LDAP, models, native-query lockdown `not_started`. Tracker: [STATUS.md](../STATUS.md).

## Local

After `make bootstrap`:

1. Open http://127.0.0.1:3000
2. Sign in with `.env` `MB_ADMIN_*`
3. Browse **ClickHouse marts** → `insumo_evento`, `trazabilidad_gap`, `indicador_cobertura`

The `metabase` ClickHouse user has no grant on `raw`.

## Production still to do

- Groups mapped to areas (Farmacia, Facturación, Dirección), collection permissions
- LDAP if the institution runs AD
- Metabase **models** over marts so users compose from governed definitions
- Native query permissions off for general users; ClickHouse profile is the backstop

## How to check

```bash
make setup-metabase
make verify          # asserts the ClickHouse marts database exists in Metabase
```

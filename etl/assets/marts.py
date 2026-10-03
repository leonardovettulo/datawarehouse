"""Marts rebuilt from raw into a shadow table, then swapped in atomically.

Readers (Metabase) see either the previous complete mart or the new one, never an
empty or half-written table. A failed rebuild leaves the previous mart in place.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from dagster import Failure, MaterializeResult, asset

from etl.assets.raw import raw_assets
from etl.resources import ClickHouseResource

RAW_DEPS = raw_assets

EVENTO_DDL = """
CREATE TABLE {table}
(
    evento_id String,
    trazabilidad_id String,
    stage LowCardinality(String),
    insumo_codigo LowCardinality(String),
    insumo_nombre String,
    fecha Date,
    cantidad Float64,
    unidad LowCardinality(String),
    documento String,
    origen_tabla LowCardinality(String),
    origen_id Int32,
    paciente_ref String,
    _built_at DateTime64(6, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(fecha)
ORDER BY (insumo_codigo, fecha, stage, origen_id)
"""

GAP_DDL = """
CREATE TABLE {table}
(
    insumo_codigo LowCardinality(String),
    insumo_nombre String,
    periodo Date,
    qty_compra Float64,
    qty_entrega Float64,
    qty_hc Float64,
    qty_facturacion Float64,
    delta_compra_entrega Float64,
    delta_entrega_hc Float64,
    delta_entrega_facturacion Float64,
    motivo LowCardinality(String),
    _built_at DateTime64(6, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(periodo)
ORDER BY (insumo_codigo, periodo)
"""

INDICADOR_DDL = """
CREATE TABLE {table}
(
    indicador LowCardinality(String),
    periodo Date,
    numerador Float64,
    denominador Float64,
    valor Float64,
    definicion String,
    _built_at DateTime64(6, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(periodo)
ORDER BY (indicador, periodo)
"""

# raw is append-only: every extracted version of a source row is kept. Marts read
# only the current version of each id, otherwise an UPDATE at the source (or a
# batch re-inserted after a failed watermark write) is counted twice.
EVENTO_SQL = r"""
SELECT
    concat('compra-', toString(id)) AS evento_id,
    concat(insumo_codigo, '-', formatDateTime(fecha, '%Y-%m')) AS trazabilidad_id,
    'compra' AS stage,
    insumo_codigo,
    insumo_nombre,
    fecha,
    cantidad,
    unidad,
    nro_comprobante AS documento,
    'compras' AS origen_tabla,
    id AS origen_id,
    '' AS paciente_ref,
    now64(6) AS _built_at
FROM (SELECT * FROM raw.compras ORDER BY updated_at DESC, _ingested_at DESC LIMIT 1 BY id)
UNION ALL
SELECT
    concat('entrega-', toString(id)),
    concat(insumo_codigo, '-', formatDateTime(fecha, '%Y-%m')),
    'entrega_farmacia',
    insumo_codigo,
    insumo_nombre,
    fecha,
    cantidad,
    unidad,
    nro_remito,
    'entregas_farmacia',
    id,
    '',
    now64(6)
FROM (SELECT * FROM raw.entregas_farmacia ORDER BY updated_at DESC, _ingested_at DESC LIMIT 1 BY id)
UNION ALL
SELECT
    concat('hc-', toString(id)),
    concat(insumo_codigo, '-', formatDateTime(fecha, '%Y-%m')),
    'hc',
    insumo_codigo,
    insumo_nombre,
    fecha,
    cantidad,
    unidad,
    profesional,
    'hc_registros',
    id,
    lower(hex(SHA256(concat(nro_historia, {pepper:String})))),
    now64(6)
FROM (SELECT * FROM raw.hc_registros ORDER BY updated_at DESC, _ingested_at DESC LIMIT 1 BY id)
UNION ALL
SELECT
    concat('facturacion-', toString(id)),
    concat(insumo_codigo, '-', formatDateTime(fecha, '%Y-%m')),
    'facturacion',
    insumo_codigo,
    insumo_nombre,
    fecha,
    cantidad,
    unidad,
    nro_factura,
    'facturacion',
    id,
    '',
    now64(6)
FROM (SELECT * FROM raw.facturacion ORDER BY updated_at DESC, _ingested_at DESC LIMIT 1 BY id)
"""

GAP_SQL = """
SELECT
    insumo_codigo,
    insumo_nombre,
    periodo,
    qty_compra,
    qty_entrega,
    qty_hc,
    qty_facturacion,
    qty_compra - qty_entrega AS delta_compra_entrega,
    qty_entrega - qty_hc AS delta_entrega_hc,
    qty_entrega - qty_facturacion AS delta_entrega_facturacion,
    multiIf(
        qty_entrega = 0, 'sin_entrega',
        qty_hc = 0 AND qty_facturacion = 0, 'no_registrado_hc_ni_facturacion',
        qty_hc = 0, 'no_registrado_hc',
        qty_facturacion = 0, 'no_registrado_facturacion',
        abs(qty_entrega - qty_hc) > 0.001 OR abs(qty_entrega - qty_facturacion) > 0.001, 'discrepancia',
        'completo'
    ) AS motivo,
    now64(6) AS _built_at
FROM
(
    SELECT
        insumo_codigo,
        any(insumo_nombre) AS insumo_nombre,
        toStartOfMonth(fecha) AS periodo,
        sumIf(cantidad, stage = 'compra') AS qty_compra,
        sumIf(cantidad, stage = 'entrega_farmacia') AS qty_entrega,
        sumIf(cantidad, stage = 'hc') AS qty_hc,
        sumIf(cantidad, stage = 'facturacion') AS qty_facturacion
    FROM marts.insumo_evento
    GROUP BY insumo_codigo, periodo
)
"""

INDICADOR_SQL = """
SELECT
    indicador,
    periodo,
    numerador,
    denominador,
    if(denominador = 0, 0, numerador / denominador) AS valor,
    definicion,
    now64(6) AS _built_at
FROM
(
    SELECT
        'cobertura_hc' AS indicador,
        periodo,
        sum(qty_hc) AS numerador,
        sum(qty_entrega) AS denominador,
        'Proporción de cantidad entregada por Farmacia que tiene registro en Historia Clínica. Hueco de captura, no necesariamente pérdida física.' AS definicion
    FROM marts.trazabilidad_gap
    GROUP BY periodo
    UNION ALL
    SELECT
        'cobertura_facturacion',
        periodo,
        sum(qty_facturacion),
        sum(qty_entrega),
        'Proporción de cantidad entregada por Farmacia que tiene registro de facturación.'
    FROM marts.trazabilidad_gap
    GROUP BY periodo
)
"""


def _pepper() -> str:
    pepper = os.environ.get("PSEUDONYM_PEPPER", "")
    if not pepper:
        raise Failure("PSEUDONYM_PEPPER is not set; refusing to build marts with an unknown pseudonym key.")
    return pepper


def _rebuild(ch, name: str, ddl: str, select_sql: str, parameters: dict | None = None) -> int:
    """Build marts.<name>__new from the current DDL, then swap it in atomically.

    Creating the shadow table from the DDL in code (not `AS marts.<name>`) means a
    schema change in this file takes effect on the next run.
    """
    target = f"marts.{name}"
    shadow = f"marts.{name}__new"
    ch.command(f"DROP TABLE IF EXISTS {shadow}")
    ch.command(ddl.format(table=shadow))
    ch.command(f"INSERT INTO {shadow}\n{select_sql}", parameters=parameters)
    if int(ch.command(f"EXISTS TABLE {target}")):
        ch.command(f"EXCHANGE TABLES {shadow} AND {target}")
        ch.command(f"DROP TABLE {shadow}")
    else:
        ch.command(f"RENAME TABLE {shadow} TO {target}")
    return int(ch.query(f"SELECT count() FROM {target}").result_rows[0][0])


@asset(
    group_name="marts",
    compute_kind="clickhouse",
    deps=RAW_DEPS,
    description="Normalized event chain: compra → entrega → HC → facturación. Patient ids hashed at this boundary.",
)
def marts_insumo_evento(
    context,
    clickhouse: ClickHouseResource,
) -> MaterializeResult:
    count = _rebuild(
        clickhouse.client(), "insumo_evento", EVENTO_DDL, EVENTO_SQL, parameters={"pepper": _pepper()}
    )
    context.log.info("marts.insumo_evento rows=%s", count)
    return MaterializeResult(metadata={"rows": count, "built_at": str(datetime.now(timezone.utc))})


@asset(
    group_name="marts",
    compute_kind="clickhouse",
    deps=[marts_insumo_evento],
    description="Per insumo and month: quantities at each stage, with motivo distinguishing missing capture from mismatch.",
)
def marts_trazabilidad_gap(
    context,
    clickhouse: ClickHouseResource,
) -> MaterializeResult:
    count = _rebuild(clickhouse.client(), "trazabilidad_gap", GAP_DDL, GAP_SQL)
    context.log.info("marts.trazabilidad_gap rows=%s", count)
    return MaterializeResult(metadata={"rows": count})


@asset(
    group_name="marts",
    compute_kind="clickhouse",
    deps=[marts_trazabilidad_gap],
    description="Executive indicators with a written definition stored next to the number.",
)
def marts_indicador_cobertura(
    context,
    clickhouse: ClickHouseResource,
) -> MaterializeResult:
    count = _rebuild(clickhouse.client(), "indicador_cobertura", INDICADOR_DDL, INDICADOR_SQL)
    context.log.info("marts.indicador_cobertura rows=%s", count)
    return MaterializeResult(metadata={"rows": count})

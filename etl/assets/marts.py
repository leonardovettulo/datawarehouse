"""Marts rebuilt from raw by truncate-and-reload (partition replacement comes later)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from dagster import MaterializeResult, asset

from etl.assets.raw import raw_assets
from etl.resources import ClickHouseResource

RAW_DEPS = raw_assets

EVENTO_DDL = """
CREATE TABLE IF NOT EXISTS marts.insumo_evento
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
CREATE TABLE IF NOT EXISTS marts.trazabilidad_gap
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
CREATE TABLE IF NOT EXISTS marts.indicador_cobertura
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

EVENTO_SQL = r"""
INSERT INTO marts.insumo_evento
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
FROM raw.compras
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
FROM raw.entregas_farmacia
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
FROM raw.hc_registros
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
FROM raw.facturacion
"""

GAP_SQL = """
INSERT INTO marts.trazabilidad_gap
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
INSERT INTO marts.indicador_cobertura
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
    ch = clickhouse.client()
    pepper = os.environ.get("PSEUDONYM_PEPPER", "local-dev-pepper-not-for-prod")
    ch.command(EVENTO_DDL)
    ch.command("TRUNCATE TABLE IF EXISTS marts.insumo_evento")
    ch.command(EVENTO_SQL, parameters={"pepper": pepper})
    count = int(ch.query("SELECT count() FROM marts.insumo_evento").result_rows[0][0])
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
    ch = clickhouse.client()
    ch.command(GAP_DDL)
    ch.command("TRUNCATE TABLE IF EXISTS marts.trazabilidad_gap")
    ch.command(GAP_SQL)
    count = int(ch.query("SELECT count() FROM marts.trazabilidad_gap").result_rows[0][0])
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
    ch = clickhouse.client()
    ch.command(INDICADOR_DDL)
    ch.command("TRUNCATE TABLE IF EXISTS marts.indicador_cobertura")
    ch.command(INDICADOR_SQL)
    count = int(ch.query("SELECT count() FROM marts.indicador_cobertura").result_rows[0][0])
    context.log.info("marts.indicador_cobertura rows=%s", count)
    return MaterializeResult(metadata={"rows": count})

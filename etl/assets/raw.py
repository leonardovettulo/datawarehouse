"""Per-table extract: watermark → source delta → parquet → ClickHouse raw.

The delta is streamed in chunks (EXTRACT_CHUNK_ROWS, default 50 000): each chunk
is appended to the batch parquet file, then inserted into raw. The watermark only
advances after every chunk landed. If a run dies half-way, the next run re-reads
the same delta; marts read the latest version per id, so repeats don't count twice.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from dagster import AssetCheckResult, AssetCheckSeverity, MaterializeResult, asset, asset_check

from etl.resources import ArchiveResource, ClickHouseResource, SourceDBResource

WATERMARK_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
DEFAULT_CHUNK_ROWS = 50_000

RAW_DDL = """
CREATE TABLE IF NOT EXISTS raw.{table}
(
    id Int32,
    insumo_codigo String,
    insumo_nombre String,
    fecha Date,
    cantidad Float64,
    unidad String,
    {extra_cols}
    updated_at DateTime64(6, 'UTC'),
    _ingested_at DateTime64(6, 'UTC'),
    _batch_id String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(fecha)
ORDER BY (id, _ingested_at)
"""


@dataclass(frozen=True)
class SourceTable:
    name: str
    extra_ch_cols: str
    extra_source_cols: tuple[str, ...]


TABLES = (
    SourceTable(
        name="compras",
        extra_ch_cols="proveedor String,\n    nro_comprobante String,",
        extra_source_cols=("proveedor", "nro_comprobante"),
    ),
    SourceTable(
        name="entregas_farmacia",
        extra_ch_cols="sector_destino String,\n    nro_remito String,",
        extra_source_cols=("sector_destino", "nro_remito"),
    ),
    SourceTable(
        name="hc_registros",
        extra_ch_cols="nro_historia String,\n    profesional String,",
        extra_source_cols=("nro_historia", "profesional"),
    ),
    SourceTable(
        name="facturacion",
        extra_ch_cols="nro_factura String,\n    obra_social String,",
        extra_source_cols=("nro_factura", "obra_social"),
    ),
)

BASE_COLS = (
    "id",
    "insumo_codigo",
    "insumo_nombre",
    "fecha",
    "cantidad",
    "unidad",
)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _coerce(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return _aware(value)
    return value


def _last_watermark(ch, table_name: str) -> datetime:
    result = ch.query(
        "SELECT watermark FROM raw.ingest_state "
        "WHERE table_name = {name:String} "
        "ORDER BY last_ingested_at DESC LIMIT 1",
        parameters={"name": table_name},
    )
    if not result.result_rows:
        return WATERMARK_EPOCH
    return _aware(result.result_rows[0][0])


def _arrow_schema(spec: SourceTable):
    """Explicit schema matching RAW_DDL, so every chunk of a batch shares one parquet schema."""
    import pyarrow as pa

    ts = pa.timestamp("us", tz="UTC")
    fields = [
        ("id", pa.int32()),
        ("insumo_codigo", pa.string()),
        ("insumo_nombre", pa.string()),
        ("fecha", pa.date32()),
        ("cantidad", pa.float64()),
        ("unidad", pa.string()),
        *[(col, pa.string()) for col in spec.extra_source_cols],
        ("updated_at", ts),
        ("_ingested_at", ts),
        ("_batch_id", pa.string()),
    ]
    return pa.schema(fields)


def _parquet_path(archive_root: str, table: str, batch_id: str, ingested_at: datetime) -> Path:
    directory = (
        Path(archive_root)
        / "source"
        / table
        / ingested_at.strftime("%Y")
        / ingested_at.strftime("%m")
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{ingested_at.strftime('%Y-%m-%d')}_{batch_id}.parquet.zst"


def _chunk_rows() -> int:
    return int(os.environ.get("EXTRACT_CHUNK_ROWS", DEFAULT_CHUNK_ROWS))


def _make_raw_asset(spec: SourceTable):
    @asset(
        name=f"raw_{spec.name}",
        group_name="raw",
        compute_kind="clickhouse",
        description=f"Incremental extract of source.{spec.name} into raw.{spec.name} (parquet first).",
    )
    def _extract(
        context,
        source_db: SourceDBResource,
        clickhouse: ClickHouseResource,
        archive: ArchiveResource,
    ) -> MaterializeResult:
        ch = clickhouse.client()
        ch.command(RAW_DDL.format(table=spec.name, extra_cols=spec.extra_ch_cols))

        watermark = _last_watermark(ch, spec.name)
        batch_id = uuid4().hex
        ingested_at = datetime.now(timezone.utc)
        source_cols = BASE_COLS + spec.extra_source_cols + ("updated_at",)
        insert_cols = source_cols + ("_ingested_at", "_batch_id")
        updated_at_index = source_cols.index("updated_at")

        context.log.info("Extracting %s after watermark %s (batch %s)", spec.name, watermark, batch_id)

        import pyarrow as pa
        import pyarrow.parquet as pq

        schema = _arrow_schema(spec)
        sql = (
            f"SELECT {', '.join(source_cols)} FROM {spec.name} "
            "WHERE updated_at > %s ORDER BY updated_at, id"
        )
        parquet_path = None
        writer = None
        total = 0
        new_watermark = watermark
        try:
            for fetched in source_db.stream(sql, (watermark,), _chunk_rows()):
                rows = [tuple(_coerce(v) for v in row) + (ingested_at, batch_id) for row in fetched]
                if writer is None:
                    parquet_path = _parquet_path(archive.root, spec.name, batch_id, ingested_at)
                    writer = pq.ParquetWriter(parquet_path, schema, compression="zstd")
                columns = {name: [row[i] for row in rows] for i, name in enumerate(insert_cols)}
                writer.write_table(pa.table(columns, schema=schema))
                ch.insert(f"raw.{spec.name}", rows, column_names=list(insert_cols))
                new_watermark = max(new_watermark, max(row[updated_at_index] for row in rows))
                total += len(rows)
                context.log.info("%s: %s rows so far", spec.name, total)
        finally:
            if writer is not None:
                writer.close()

        if total == 0:
            context.log.info("No new rows for %s", spec.name)
            return MaterializeResult(
                metadata={"table": spec.name, "rows": 0, "watermark": str(watermark), "batch_id": batch_id}
            )

        context.log.info("Wrote %s rows to %s", total, parquet_path)
        ch.insert(
            "raw.ingest_state",
            [[spec.name, new_watermark, batch_id, ingested_at, total]],
            column_names=["table_name", "watermark", "last_batch_id", "last_ingested_at", "rows_inserted"],
        )

        return MaterializeResult(
            metadata={
                "table": spec.name,
                "rows": total,
                "batch_id": batch_id,
                "parquet": str(parquet_path),
                "watermark_advanced_to": str(new_watermark),
            }
        )

    return _extract


raw_assets = [_make_raw_asset(spec) for spec in TABLES]


def _make_reconcile_check(spec: SourceTable, raw_asset):
    @asset_check(
        asset=raw_asset,
        name="matches_source",
        blocking=True,
        description=(
            f"Every source.{spec.name} row up to the current watermark is in raw.{spec.name}. "
            "Missing rows fail the run before marts are rebuilt; extra ids (deleted at the "
            "source) only warn."
        ),
    )
    def _check(source_db: SourceDBResource, clickhouse: ClickHouseResource) -> AssetCheckResult:
        ch = clickhouse.client()
        watermark = _last_watermark(ch, spec.name)
        # Bounded by the watermark so rows that arrive at the source mid-run are not
        # reported as missing; they belong to the next run.
        with source_db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {spec.name} WHERE updated_at <= %s", (watermark,))
                source_count = int(cur.fetchone()[0])
        raw_count = int(ch.query(f"SELECT uniqExact(id) FROM raw.{spec.name}").result_rows[0][0])

        metadata = {"source_rows": source_count, "raw_distinct_ids": raw_count, "watermark": str(watermark)}
        if raw_count < source_count:
            return AssetCheckResult(
                passed=False,
                severity=AssetCheckSeverity.ERROR,
                description=f"{source_count - raw_count} source rows missing from raw.{spec.name}",
                metadata=metadata,
            )
        if raw_count > source_count:
            return AssetCheckResult(
                passed=False,
                severity=AssetCheckSeverity.WARN,
                description=f"{raw_count - source_count} ids in raw.{spec.name} no longer exist at the source",
                metadata=metadata,
            )
        return AssetCheckResult(passed=True, metadata=metadata)

    return _check


raw_checks = [_make_reconcile_check(spec, raw_asset) for spec, raw_asset in zip(TABLES, raw_assets)]


@asset(
    group_name="ops",
    compute_kind="postgres",
    description="Phase 3 deliverable: row counts from the source written into ClickHouse.",
)
def source_row_counts(
    context,
    source_db: SourceDBResource,
    clickhouse: ClickHouseResource,
) -> MaterializeResult:
    captured_at = datetime.now(timezone.utc)
    counts: dict[str, int] = {}
    with source_db.connect() as conn:
        with conn.cursor() as cur:
            for spec in TABLES:
                cur.execute(f"SELECT count(*) FROM {spec.name}")
                counts[spec.name] = int(cur.fetchone()[0])

    ch = clickhouse.client()
    rows = [[captured_at, name, count] for name, count in counts.items()]
    ch.insert(
        "raw.source_row_counts",
        rows,
        column_names=["captured_at", "table_name", "row_count"],
    )
    context.log.info("Source counts: %s", counts)
    return MaterializeResult(metadata={"captured_at": str(captured_at), **counts})

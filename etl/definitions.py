from dagster import (
    AssetSelection,
    Definitions,
    ScheduleDefinition,
    define_asset_job,
)

from etl.assets.marts import marts_indicador_cobertura, marts_insumo_evento, marts_trazabilidad_gap
from etl.assets.raw import raw_assets, source_row_counts
from etl.resources import default_archive, default_clickhouse, default_source

all_assets = [
    source_row_counts,
    *raw_assets,
    marts_insumo_evento,
    marts_trazabilidad_gap,
    marts_indicador_cobertura,
]

ingest_and_marts = define_asset_job(
    "ingest_and_marts",
    selection=AssetSelection.assets(*all_assets),
    description="Extract source deltas into raw, then rebuild marts from raw.",
)

nightly_ingest = ScheduleDefinition(
    name="nightly_ingest",
    job=ingest_and_marts,
    cron_schedule="0 6 * * *",
    execution_timezone="America/Argentina/Cordoba",
)

defs = Definitions(
    assets=all_assets,
    jobs=[ingest_and_marts],
    schedules=[nightly_ingest],
    resources={
        "source_db": default_source(),
        "clickhouse": default_clickhouse(),
        "archive": default_archive(),
    },
)

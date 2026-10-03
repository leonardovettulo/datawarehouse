from dagster import AssetSelection, DefaultScheduleStatus, ScheduleDefinition, define_asset_job

from etl.assets.marts import marts_indicador_cobertura, marts_insumo_evento, marts_trazabilidad_gap
from etl.assets.raw import raw_assets, source_row_counts

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

# Schedules default to STOPPED in Dagster; without RUNNING a fresh instance
# (new server, wiped dagster db) would silently never run the nightly.
nightly_ingest = ScheduleDefinition(
    name="nightly_ingest",
    job=ingest_and_marts,
    cron_schedule="0 6 * * *",
    execution_timezone="America/Argentina/Cordoba",
    default_status=DefaultScheduleStatus.RUNNING,
)

from dagster import Definitions

from etl.alerts import alert_on_run_failure, heartbeat_on_success
from etl.assets.raw import raw_checks
from etl.jobs import all_assets, ingest_and_marts, nightly_ingest
from etl.resources import default_archive, default_clickhouse, default_source

defs = Definitions(
    assets=all_assets,
    asset_checks=raw_checks,
    jobs=[ingest_and_marts],
    schedules=[nightly_ingest],
    sensors=[alert_on_run_failure, heartbeat_on_success],
    resources={
        "source_db": default_source(),
        "clickhouse": default_clickhouse(),
        "archive": default_archive(),
    },
)

from dagster import (
    AssetExecutionContext,
    DailyPartitionsDefinition,
    Definitions,
    MaterializeResult,
    ScheduleDefinition,
    asset,
    define_asset_job,
    materialize,
)

daily_partitions = DailyPartitionsDefinition(start_date="2025-01-01")


@asset(partitions_def=daily_partitions, description="Example asset — replace with real pipelines.")
def hello_world(context: AssetExecutionContext) -> MaterializeResult:
    partition_key = context.partition_key
    message = f"Hello from partition {partition_key}"
    context.log.info(message)
    return MaterializeResult(metadata={"message": message, "partition": partition_key})


hello_job = define_asset_job("hello_job", selection=[hello_world])

daily_hello_schedule = ScheduleDefinition(
    job=hello_job,
    cron_schedule="0 6 * * *",
    name="daily_hello",
)


defs = Definitions(
    assets=[hello_world],
    jobs=[hello_job],
    schedules=[daily_hello_schedule],
)

# Local dev without Docker: `dagster dev -m my_pipelines.definitions`
if __name__ == "__main__":
    materialize([hello_world])

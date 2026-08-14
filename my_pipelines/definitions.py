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
import httpx
import humanize

daily_partitions = DailyPartitionsDefinition(start_date="2025-01-01")


@asset(partitions_def=daily_partitions, description="Example asset — replace with real pipelines.")
def hello_world(context: AssetExecutionContext) -> MaterializeResult:
    partition_key = context.partition_key
    message = f"Hello from partition {partition_key}"
    context.log.info(message)
    return MaterializeResult(metadata={"message": message, "partition": partition_key})

@asset(partitions_def=daily_partitions, description="Example asset — replace with real pipelines.")
def hello_world_2(context: AssetExecutionContext) -> MaterializeResult:
    partition_key = context.partition_key
    message = f"Hello from partition {partition_key}"
    context.log.info(message)
    return MaterializeResult(metadata={"message": message, "partition": partition_key})


@asset(description="Second asset to verify reload works.")
def goodbye_world(context: AssetExecutionContext) -> MaterializeResult:
    message = "Goodbye — deployed after reload"
    context.log.info(message)
    return MaterializeResult(metadata={"message": message})


@asset(description="Third asset — simple health check.")
def health_check(context: AssetExecutionContext) -> MaterializeResult:
    status = "ok"
    payload_bytes = 1_048_576
    context.log.info("health_check: %s (%s)", status, humanize.naturalsize(payload_bytes))
    return MaterializeResult(
        metadata={"status": status, "payload": humanize.naturalsize(payload_bytes)}
    )


@asset(description="HTTP reachability check using httpx.")
def http_ping(context: AssetExecutionContext) -> MaterializeResult:
    url = "https://httpbin.org/get"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    context.log.info("GET %s -> %s", url, response.status_code)
    return MaterializeResult(metadata={"url": url, "status_code": response.status_code})


hello_job = define_asset_job("hello_job", selection=[hello_world])
hello_job_2 = define_asset_job("hello_job_2", selection=[hello_world_2])
goodbye_job = define_asset_job("goodbye_job", selection=[goodbye_world])
health_check_job = define_asset_job("health_check_job", selection=[health_check])
http_ping_job = define_asset_job("http_ping_job", selection=[http_ping])

daily_hello_schedule = ScheduleDefinition(
    job=hello_job,
    cron_schedule="0 6 * * *",
    name="daily_hello",
)


defs = Definitions(
    assets=[hello_world, goodbye_world, health_check, http_ping, hello_world_2],
    jobs=[hello_job, goodbye_job, health_check_job, http_ping_job, hello_job_2],
    schedules=[daily_hello_schedule],
)

# Local dev without Docker: `dagster dev -m my_pipelines.definitions`
if __name__ == "__main__":
    materialize([hello_world])

"""Pipeline alerting through a heartbeat monitor (Better Stack).

PIPELINE_HEARTBEAT_URL is pinged when ingest_and_marts succeeds and `<url>/fail`
is pinged when any run fails. Better Stack opens an incident on /fail right away,
and also when no success ping arrives within the heartbeat period, which catches
"the schedule never ran" — something a failure sensor cannot see. Better Stack
handles routing (email, SMS, app). Healthchecks.io accepts the same calls.

Only job names, run ids and error messages are sent; never data rows.
"""

from __future__ import annotations

import os
import urllib.request

from dagster import (
    DagsterRunStatus,
    DefaultSensorStatus,
    RunFailureSensorContext,
    RunStatusSensorContext,
    run_failure_sensor,
    run_status_sensor,
)

from etl.jobs import ingest_and_marts


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def ping_heartbeat(failed: bool = False, body: str = "") -> bool:
    """POST to PIPELINE_HEARTBEAT_URL (or <url>/fail). Returns False when not configured."""
    url = _env("PIPELINE_HEARTBEAT_URL").rstrip("/")
    if not url:
        return False
    if failed:
        url += "/fail"
    request = urllib.request.Request(url, data=body.encode()[:10_000], method="POST")
    with urllib.request.urlopen(request, timeout=15):
        pass
    return True


def _run_url(run_id: str) -> str:
    base = _env("DAGSTER_BASE_URL").rstrip("/")
    return f"{base}/runs/{run_id}" if base else f"run id {run_id}"


@run_failure_sensor(
    name="alert_on_run_failure",
    description="Heartbeat /fail for every failed run in this code location.",
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=30,
)
def alert_on_run_failure(context: RunFailureSensorContext):
    run = context.dagster_run
    error = context.failure_event.message or "(no error message)"
    body = f"Job: {run.job_name}\nRun: {_run_url(run.run_id)}\n\n{error}\n"
    # A network error raises, which fails the sensor tick; the run is retried next tick.
    if not ping_heartbeat(failed=True, body=body):
        context.log.warning("PIPELINE_HEARTBEAT_URL is not set; failure not reported.")


@run_status_sensor(
    name="heartbeat_on_success",
    description="Pings PIPELINE_HEARTBEAT_URL when ingest_and_marts succeeds.",
    run_status=DagsterRunStatus.SUCCESS,
    monitored_jobs=[ingest_and_marts],
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=30,
)
def heartbeat_on_success(context: RunStatusSensorContext):
    if not ping_heartbeat(body=f"{context.dagster_run.job_name} {context.dagster_run.run_id}"):
        context.log.warning("PIPELINE_HEARTBEAT_URL is not set; skipped.")

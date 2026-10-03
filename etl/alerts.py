"""Pipeline alerting: email on run failure, heartbeat on nightly success.

Two independent channels, both configured by environment and both optional:

- Email (ALERT_SMTP_*, ALERT_EMAIL_*): one message per failed run, any job.
- Heartbeat (PIPELINE_HEARTBEAT_URL): pinged when ingest_and_marts succeeds and
  `<url>/fail` when any run fails. Works with Better Stack heartbeats and
  Healthchecks.io. The monitoring service alerts when no success ping arrives
  within its period, which also catches "the schedule never ran" — something a
  failure sensor cannot see.

Only job names, run ids and error messages are sent; never data rows.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage

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


def send_email(subject: str, body: str) -> bool:
    """Send via ALERT_SMTP_HOST. Returns False (and does nothing) when not configured."""
    host = _env("ALERT_SMTP_HOST")
    recipients = [r.strip() for r in _env("ALERT_EMAIL_TO").split(",") if r.strip()]
    if not host or not recipients:
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _env("ALERT_EMAIL_FROM") or "dagster@localhost"
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    port = int(_env("ALERT_SMTP_PORT") or 587)
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if _env("ALERT_SMTP_STARTTLS").lower() not in ("0", "no", "false"):
            smtp.starttls(context=ssl.create_default_context())
        user = _env("ALERT_SMTP_USER")
        if user:
            smtp.login(user, _env("ALERT_SMTP_PASSWORD"))
        smtp.send_message(message)
    return True


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
    description="Email + heartbeat /fail for every failed run in this code location.",
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=30,
)
def alert_on_run_failure(context: RunFailureSensorContext):
    run = context.dagster_run
    error = context.failure_event.message or "(no error message)"
    subject = f"[DW] Dagster run failed: {run.job_name}"
    body = f"Job: {run.job_name}\nRun: {_run_url(run.run_id)}\n\n{error}\n"

    # Try both channels before raising, so one broken channel doesn't silence the other.
    # A raised error fails the sensor tick and the run is retried on the next tick.
    errors = []
    for name, send in (("email", lambda: send_email(subject, body)), ("heartbeat", lambda: ping_heartbeat(True, body))):
        try:
            if not send():
                context.log.warning(f"Alert channel {name} is not configured; skipped.")
        except Exception as exc:  # noqa: BLE001 - report every channel failure
            errors.append(f"{name}: {exc}")
    if errors:
        raise RuntimeError("Could not deliver failure alert: " + "; ".join(errors))


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

"""Operational helpers that run inside the Dagster image.

  fail-orphans   Mark in-progress runs as failed. Run only at daemon startup:
                 with DefaultRunLauncher every run worker is a child of the
                 daemon container, so after a restart none of them is alive.
  wait-idle      Block until no run is in progress (used by scripts/deploy.sh).
  launch         Submit a job through the run queue and optionally wait for it.
"""

from __future__ import annotations

import argparse
import sys
import time

from dagster import DagsterInstance, DagsterRunStatus
from dagster._core.storage.dagster_run import IN_PROGRESS_RUN_STATUSES, RunsFilter


def _in_progress(instance: DagsterInstance):
    return instance.get_runs(filters=RunsFilter(statuses=IN_PROGRESS_RUN_STATUSES))


def fail_orphans(_args) -> int:
    instance = DagsterInstance.get()
    runs = _in_progress(instance)
    for run in runs:
        instance.report_run_failed(
            run,
            "Run worker did not survive a dagster-daemon restart (deploy, reboot or crash). "
            "Marked as failed at daemon startup so the run queue is not blocked.",
        )
        print(f"Marked orphaned run {run.run_id} ({run.job_name}, was {run.status.value}) as failed.")
    if not runs:
        print("No orphaned runs.")
    return 0


def wait_idle(args) -> int:
    instance = DagsterInstance.get()
    deadline = time.monotonic() + args.timeout
    announced = False
    while True:
        runs = _in_progress(instance)
        if not runs:
            print("No runs in progress.")
            return 0
        if time.monotonic() > deadline:
            names = ", ".join(f"{r.job_name} ({r.run_id[:8]})" for r in runs)
            print(f"Still running after {args.timeout}s: {names}", file=sys.stderr)
            return 1
        if not announced:
            names = ", ".join(f"{r.job_name} ({r.run_id[:8]})" for r in runs)
            print(f"Waiting for in-progress runs to finish: {names}")
            announced = True
        time.sleep(args.poll)


def launch(args) -> int:
    from dagster_graphql import DagsterGraphQLClient

    client = DagsterGraphQLClient("localhost", port_number=3000)
    run_id = client.submit_job_execution(args.job)
    print(f"Queued {args.job} run {run_id}")
    if not args.wait:
        return 0

    finished = {DagsterRunStatus.SUCCESS, DagsterRunStatus.FAILURE, DagsterRunStatus.CANCELED}
    status = client.get_run_status(run_id)
    while status not in finished:
        time.sleep(2)
        status = client.get_run_status(run_id)
    print(f"Run {run_id} finished: {status.value}")
    return 0 if status == DagsterRunStatus.SUCCESS else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fail-orphans").set_defaults(func=fail_orphans)

    p = sub.add_parser("wait-idle")
    p.add_argument("--timeout", type=int, default=1800, help="seconds before giving up (default 1800)")
    p.add_argument("--poll", type=int, default=10)
    p.set_defaults(func=wait_idle)

    p = sub.add_parser("launch")
    p.add_argument("job")
    p.add_argument("--wait", action="store_true")
    p.set_defaults(func=launch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Wait until Dagster, Metabase, and ClickHouse answer locally."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

TIMEOUT_S = int(os.environ.get("WAIT_TIMEOUT", "180"))
DAGSTER_URL = os.environ.get("DAGSTER_URL", "http://127.0.0.1:3030")
METABASE_URL = os.environ.get("METABASE_URL", "http://127.0.0.1:3000/api/health")


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def _clickhouse_ok() -> bool:
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                "dw-local",
                "-f",
                "platform/compose.yaml",
                "-f",
                "compose.yaml",
                "--project-directory",
                ".",
                "exec",
                "-T",
                "clickhouse",
                "clickhouse-client",
                "--user",
                "default",
                "--password",
                os.environ.get("CH_ADMIN_PASSWORD", ""),
                "--query",
                "SELECT 1",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and "1" in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def main() -> int:
    deadline = time.time() + TIMEOUT_S
    checks = {
        "dagster": lambda: _http_ok(DAGSTER_URL),
        "metabase": lambda: _http_ok(METABASE_URL),
        "clickhouse": _clickhouse_ok,
    }
    pending = set(checks)
    print(f"Waiting up to {TIMEOUT_S}s for {', '.join(sorted(pending))} ...")
    while pending and time.time() < deadline:
        for name in list(pending):
            if checks[name]():
                print(f"  {name}: ok")
                pending.remove(name)
        if pending:
            time.sleep(3)
    if pending:
        print("Still down: " + ", ".join(sorted(pending)), file=sys.stderr)
        return 1
    print("Stack is reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

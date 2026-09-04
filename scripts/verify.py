#!/usr/bin/env python3
"""Check that raw, marts, parquet archive, and Metabase are populated."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "compose",
    "-p",
    "dw-local",
    "-f",
    "platform/compose.yaml",
    "-f",
    "compose.yaml",
    "--project-directory",
    str(ROOT),
]


def _ch(sql: str) -> str:
    result = subprocess.run(
        COMPOSE
        + [
            "exec",
            "-T",
            "clickhouse",
            "clickhouse-client",
            "--user",
            "default",
            "--password",
            os.environ["CH_ADMIN_PASSWORD"],
            "--query",
            sql,
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise SystemExit(f"ClickHouse query failed:\n{result.stderr}\n{sql}")
    return result.stdout.strip()


def _count(table: str) -> int:
    return int(_ch(f"SELECT count() FROM {table}"))


def main() -> int:
    expected = {
        "raw.compras": 30,
        "raw.entregas_farmacia": 50,
        "raw.hc_registros": None,
        "raw.facturacion": None,
        "marts.insumo_evento": None,
        "marts.trazabilidad_gap": None,
        "marts.indicador_cobertura": None,
    }
    failures = []
    print("ClickHouse row counts:")
    for table, want in expected.items():
        got = _count(table)
        ok = got == want if want is not None else got > 0
        mark = "ok" if ok else "FAIL"
        extra = f" (expected {want})" if want is not None else ""
        print(f"  {mark:4} {table:32} {got}{extra}")
        if not ok:
            failures.append(table)

    result = subprocess.run(
        COMPOSE
        + [
            "exec",
            "-T",
            "dagster-webserver",
            "sh",
            "-c",
            "find /srv/dw/archive -name '*.parquet.zst' | wc -l",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    parquet_count = int(result.stdout.strip() or "0")
    print(f"Parquet files: {parquet_count}")
    if parquet_count < 4:
        failures.append("parquet")

    base = os.environ.get("MB_SITE_URL", "http://127.0.0.1:3000").rstrip("/")
    login = urllib.request.Request(
        base + "/api/session",
        data=json.dumps(
            {"username": os.environ["MB_ADMIN_EMAIL"], "password": os.environ["MB_ADMIN_PASSWORD"]}
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(login, timeout=15) as response:
        session = json.loads(response.read())["id"]
    db_req = urllib.request.Request(
        base + "/api/database",
        headers={"X-Metabase-Session": session},
    )
    with urllib.request.urlopen(db_req, timeout=15) as response:
        payload = json.loads(response.read())
    databases = payload.get("data", payload)
    names = [db.get("name") for db in databases]
    print(f"Metabase databases: {names}")
    if "ClickHouse marts" not in names:
        failures.append("metabase-clickhouse")

    if failures:
        print("FAILED: " + ", ".join(failures), file=sys.stderr)
        return 1
    print("Pipeline verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

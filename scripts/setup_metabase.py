#!/usr/bin/env python3
"""Complete Metabase setup (idempotent) and attach ClickHouse marts."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("MB_SITE_URL", "http://127.0.0.1:3000").rstrip("/")
ADMIN_EMAIL = os.environ["MB_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["MB_ADMIN_PASSWORD"]
ADMIN_FIRST = os.environ.get("MB_ADMIN_FIRST_NAME", "Local")
ADMIN_LAST = os.environ.get("MB_ADMIN_LAST_NAME", "Admin")
CH_PASSWORD = os.environ["CH_METABASE_PASSWORD"]
DB_DISPLAY_NAME = "ClickHouse marts"


def _request(method: str, path: str, body=None, session: str | None = None, timeout: int = 30):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if session:
        headers["X-Metabase-Session"] = session
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"error": raw.decode(errors="replace")}
        return exc.code, parsed


def _wait_health() -> None:
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/health", timeout=5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(3)
    raise SystemExit("Metabase /api/health did not become ready")


def _properties():
    _, payload = _request("GET", "/api/session/properties")
    return payload


def _login() -> str:
    status, payload = _request(
        "POST",
        "/api/session",
        {"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if status >= 400 or "id" not in payload:
        raise SystemExit(f"Metabase login failed ({status}): {payload}")
    return payload["id"]


def _setup_if_needed() -> str:
    props = _properties()
    token = props.get("setup-token")
    if not token:
        print("Metabase already set up.")
        return _login()

    status, payload = _request(
        "POST",
        "/api/setup",
        {
            "token": token,
            "user": {
                "first_name": ADMIN_FIRST,
                "last_name": ADMIN_LAST,
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
            },
            "prefs": {
                "site_name": "DW Local",
                "site_locale": "es",
                "allow_tracking": False,
            },
        },
        timeout=60,
    )
    if status >= 400:
        raise SystemExit(f"Metabase setup failed ({status}): {payload}")
    session = payload.get("id")
    if not session:
        session = _login()
    print("Metabase admin user created.")
    return session


def _clickhouse_payload() -> dict:
    return {
        "engine": "clickhouse",
        "name": DB_DISPLAY_NAME,
        "details": {
            "host": "clickhouse",
            "port": 8123,
            "user": "metabase",
            "password": CH_PASSWORD,
            "dbname": "marts",
            "ssl": False,
            "scan-all-databases": False,
        },
        "is_full_sync": True,
        "is_on_demand": False,
    }


def _ensure_clickhouse(session: str) -> None:
    status, payload = _request("GET", "/api/database", session=session)
    if status >= 400:
        raise SystemExit(f"List databases failed ({status}): {payload}")
    databases = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(databases, dict):
        databases = databases.get("data", [])
    for db in databases:
        if db.get("name") == DB_DISPLAY_NAME:
            print(f"ClickHouse database already attached (id={db.get('id')}).")
            return

    status, payload = _request("POST", "/api/database", _clickhouse_payload(), session=session, timeout=90)
    if status >= 400:
        # Metabase 0.54+ sometimes names the database list field `db` instead of `dbname`.
        retry = _clickhouse_payload()
        retry["details"].pop("dbname", None)
        retry["details"]["db"] = "marts"
        status, payload = _request("POST", "/api/database", retry, session=session, timeout=90)
    if status >= 400:
        raise SystemExit(f"Adding ClickHouse failed ({status}): {payload}")
    print(f"Attached ClickHouse marts (id={payload.get('id')}).")


def main() -> int:
    _wait_health()
    session = _setup_if_needed()
    _ensure_clickhouse(session)
    print(f"Open {BASE}  user={ADMIN_EMAIL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

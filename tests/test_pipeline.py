"""End-to-end tests against a throwaway Postgres source + ClickHouse (make test).

Tests run in file order and share one stack: each scenario builds on the state the
previous one left, the way successive nightly runs do.
"""

from __future__ import annotations

import os
from pathlib import Path

import clickhouse_connect
import psycopg
import pyarrow.parquet as pq
import pytest
from dagster import AssetCheckSeverity, DagsterInstance, DefaultScheduleStatus, Definitions, Failure

from etl.assets.marts import paciente_ref_sql
from etl.assets.raw import TABLES
from etl.definitions import defs

MARTS = ("insumo_evento", "trazabilidad_gap", "indicador_cobertura")


@pytest.fixture(scope="session")
def ch():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CH_DAGSTER_PASSWORD"],
    )


@pytest.fixture(scope="session")
def source():
    conn = psycopg.connect(
        host=os.environ["SOURCE_PG_HOST"],
        port=int(os.environ["SOURCE_PG_PORT"]),
        dbname=os.environ["SOURCE_PG_DB"],
        user=os.environ["SOURCE_PG_ADMIN_USER"],
        password=os.environ["SOURCE_PG_ADMIN_PASSWORD"],
        autocommit=True,
    )
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def instance():
    return DagsterInstance.ephemeral()


def run_pipeline(instance):
    return defs.get_job_def("ingest_and_marts").execute_in_process(instance=instance, raise_on_error=False)


def scalar(ch, sql: str):
    return ch.query(sql).result_rows[0][0]


def source_count(source, table: str) -> int:
    return source.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def compras_total(ch) -> float:
    return scalar(ch, "SELECT sum(cantidad) FROM marts.insumo_evento WHERE stage = 'compra'")


def failed_checks(result):
    return [e for e in result.get_asset_check_evaluations() if not e.passed]


@pytest.fixture(scope="session")
def first_run(instance):
    result = run_pipeline(instance)
    assert result.success, "first pipeline run failed"
    return result


# --- definitions ---------------------------------------------------------------


def test_definitions_load():
    Definitions.validate_loadable(defs)
    assert defs.get_schedule_def("nightly_ingest").default_status == DefaultScheduleStatus.RUNNING
    sensors = {s.name for s in defs.get_all_sensor_defs()} if hasattr(defs, "get_all_sensor_defs") else None
    if sensors is not None:
        assert {"alert_on_run_failure", "heartbeat_on_success"} <= sensors


def test_pseudonymize_off_by_default(monkeypatch):
    monkeypatch.delenv("PSEUDONYMIZE", raising=False)
    monkeypatch.delenv("PSEUDONYM_PEPPER", raising=False)
    expr, params = paciente_ref_sql()
    assert expr == "nro_historia"
    assert params is None


def test_pseudonymize_requires_pepper(monkeypatch):
    monkeypatch.setenv("PSEUDONYMIZE", "1")
    monkeypatch.delenv("PSEUDONYM_PEPPER", raising=False)
    with pytest.raises(Failure):
        paciente_ref_sql()


# --- pipeline scenarios ----------------------------------------------------------


def test_first_run_loads_every_source_row(first_run, ch, source):
    for spec in TABLES:
        assert scalar(ch, f"SELECT uniqExact(id) FROM raw.{spec.name}") == source_count(source, spec.name)
    for mart in MARTS:
        assert scalar(ch, f"SELECT count() FROM marts.{mart}") > 0
    assert failed_checks(first_run) == []


def test_parquet_archive_is_written_in_chunks(first_run, ch):
    files = sorted(Path(os.environ["ARCHIVE_ROOT"]).rglob("*.parquet.zst"))
    assert len(files) == len(TABLES)
    compras = next(f for f in files if "/compras/" in str(f))
    meta = pq.ParquetFile(compras).metadata
    assert meta.num_row_groups > 1, "EXTRACT_CHUNK_ROWS=7 should produce several row groups"
    assert meta.num_rows == scalar(ch, "SELECT count() FROM raw.compras")


def test_rerun_without_source_changes_is_a_noop(first_run, instance, ch):
    raw_before = scalar(ch, "SELECT count() FROM raw.compras")
    total_before = compras_total(ch)
    result = run_pipeline(instance)
    assert result.success
    assert scalar(ch, "SELECT count() FROM raw.compras") == raw_before
    assert compras_total(ch) == pytest.approx(total_before)


def test_source_update_is_counted_once(first_run, instance, ch, source):
    total_before = compras_total(ch)
    events_before = scalar(ch, "SELECT count() FROM marts.insumo_evento WHERE stage = 'compra'")
    source.execute("UPDATE compras SET cantidad = cantidad + 1, updated_at = now() WHERE id = 1")

    result = run_pipeline(instance)

    assert result.success
    assert scalar(ch, "SELECT count() FROM raw.compras WHERE id = 1") == 2, "raw keeps both versions"
    assert compras_total(ch) == pytest.approx(total_before + 1)
    assert scalar(ch, "SELECT count() FROM marts.insumo_evento WHERE stage = 'compra'") == events_before


def test_no_shadow_tables_left_behind(first_run, ch):
    leftovers = ch.query("SELECT name FROM system.tables WHERE database = 'marts' AND name LIKE '%\\_\\_new'")
    assert leftovers.result_rows == []


def test_row_deleted_at_source_only_warns(first_run, instance, source):
    source.execute("DELETE FROM facturacion WHERE id = (SELECT max(id) FROM facturacion)")

    result = run_pipeline(instance)

    assert result.success, "a source delete must not stop the pipeline"
    failed = failed_checks(result)
    assert [e.asset_key.path[-1] for e in failed] == ["raw_facturacion"]
    assert failed[0].severity == AssetCheckSeverity.WARN


def test_rows_missing_from_raw_block_marts_and_keep_previous_mart(first_run, instance, ch):
    """Runs last: deliberately corrupts raw.compras."""
    mart_before = scalar(ch, "SELECT count() FROM marts.insumo_evento")
    ch.command("ALTER TABLE raw.compras DELETE WHERE id = 2", settings={"mutations_sync": 2})

    result = run_pipeline(instance)

    assert not result.success, "a blocking ERROR check must fail the run"
    errors = [e for e in failed_checks(result) if e.severity == AssetCheckSeverity.ERROR]
    assert [e.asset_key.path[-1] for e in errors] == ["raw_compras"]
    # Marts were not rebuilt from incomplete raw, and are not empty.
    assert scalar(ch, "SELECT count() FROM marts.insumo_evento") == mart_before

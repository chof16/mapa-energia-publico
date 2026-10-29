"""Synthetic gas retail contracts; no real source extracts are published with tests."""

import copy
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from decimal import Decimal
from uuid import uuid4

import pytest
from electricity_map_domain.gas_retail import MonthlyValue, aggregate_quarter
from electricity_map_ingestion.gas_retail import Evidence, ingest, periods, read_evidence, verify_sources
from electricity_map_ingestion.gas_retail_store import TABLES, revision_id, verify_load
from pydantic import ValidationError

from scripts.export_gas_retail_postgres import copy_field, export, literal


def synthetic() -> dict:
    return {
        "version": 1,
        "reviewed_on": "2026-10-29",
        "complete": False,
        "sources": [
            {
                "source_id": "synthetic",
                "url": "https://www.cnmc.es/sites/default/files/synthetic.pdf",
                "title": "Synthetic source only",
                "publisher": "CNMC",
                "published_on": "2026-04-01",
                "retrieved_on": "2026-10-29",
                "sha256": "a" * 64,
                "file_name": "synthetic.pdf",
                "media_type": "pdf",
                "byte_size": 100,
                "page_count": 2,
                "reuse_status": "review_pending",
                "notes": "Synthetic fixture, no real source data.",
            }
        ],
        "entities": [
            {
                "gas_id": "gas-test",
                "name": "Synthetic company",
                "kind": "retailer",
                "review_note": "Synthetic reviewed identity, unrelated to R2.",
            }
        ],
        "mappings": [
            {
                "mapping_id": "map-test",
                "source_id": "synthetic",
                "observed_name": "Test name",
                "gas_id": "gas-test",
                "review_note": "Exact synthetic mapping.",
            }
        ],
        "audits": [
            {
                "period": period,
                "metric": metric,
                "status": "reviewed" if period == "2026T1" else "not_reviewed",
                "source_ids": ["synthetic"] if period == "2026T1" else [],
                "pages": [1] if period == "2026T1" else [],
                "note": "Synthetic audit.",
            }
            for period in periods()
            for metric in ("clients", "sales")
        ],
        "observations": [
            {
                "observation_id": f"obs-{metric}-{month}",
                "source_id": "synthetic",
                "mapping_id": "map-test",
                "month": f"2026-{month:02}",
                "metric": metric,
                "scope": "whole_market",
                "unit": "clients" if metric == "clients" else "MWh",
                "page": 1,
                "table_label": "Synthetic monthly table",
                "source_row": "1",
                "raw_value": str(month * 10),
                "status": "exact",
                "value": str(month * 10),
                "upper_bound": None,
                "review_note": "Synthetic reviewed scalar.",
            }
            for metric in ("clients", "sales")
            for month in (1, 2, 3)
        ],
        "catalogue": [
            {
                "gas_id": "gas-test",
                "observed_name": "Synthetic legal name",
                "designation": "gas_cur",
                "source_id": "synthetic",
                "page": 2,
                "evidence_on": "2026-04-01",
                "review_note": "Independent synthetic designation.",
            }
        ],
    }


def test_quarter_semantics_and_exact_zero():
    rows = [MonthlyValue(f"2026-{month:02}", "exact", Decimal(month * 10)) for month in (1, 2, 3)]
    assert aggregate_quarter("2026T1", "clients", rows).value == 30
    assert aggregate_quarter("2026T1", "sales", rows).value == 60
    assert aggregate_quarter("2026T1", "clients", rows[-1:]).value == 30
    missing = aggregate_quarter("2026T1", "sales", rows[1:])
    assert missing.status == "missing" and missing.value is None
    assert missing.missing_months == ("2026-01",)
    assert aggregate_quarter("2026T1", "clients", rows[:2]).value is None
    zero = aggregate_quarter("2026T1", "clients", [MonthlyValue("2026-03", "zero", Decimal(0))])
    assert zero.status == "zero" and zero.value == 0


@pytest.mark.parametrize("status", ["missing", "suppressed", "source_error", "bounded"])
def test_unavailable_and_bounded_are_not_zero(status):
    rows = [MonthlyValue("2026-03", status, upper_bound=Decimal(50) if status == "bounded" else None)]
    value = aggregate_quarter("2026T1", "clients", rows)
    assert value.status == status and value.value is None
    assert value.upper_bound == (50 if status == "bounded" else None)


def test_bounded_sales_and_error_provenance():
    rows = [
        MonthlyValue("2026-01", "exact", Decimal("0.1")),
        MonthlyValue("2026-02", "exact", Decimal("0.2")),
        MonthlyValue("2026-03", "bounded", upper_bound=Decimal(50)),
    ]
    value = aggregate_quarter("2026T1", "sales", rows)
    assert value.status == "bounded" and value.upper_bound == Decimal("50.3") and value.value is None
    rows[0] = MonthlyValue("2026-01", "source_error")
    value = aggregate_quarter("2026T1", "sales", rows)
    assert value.status == "source_error" and value.input_statuses == ("source_error", "exact", "bounded")
    with pytest.raises(ValueError, match="repeated"):
        aggregate_quarter("2026T1", "clients", [rows[-1], rows[-1]])


def test_all_90_independent_audits_and_explicit_mappings():
    data = synthetic()
    assert len(periods()) == 90 and periods()[0] == "2003T4" and periods()[-1] == "2026T1"
    assert len(Evidence.model_validate(data).audits) == 180
    invalid = copy.deepcopy(data)
    invalid["audits"].pop()
    with pytest.raises(ValidationError):
        Evidence.model_validate(invalid)
    invalid = copy.deepcopy(data)
    invalid["entities"][0]["gas_id"] = "R2-001"
    with pytest.raises(ValidationError):
        Evidence.model_validate(invalid)
    invalid = copy.deepcopy(data)
    invalid["mappings"][0]["source_id"] = "unreviewed-source"
    with pytest.raises(ValidationError):
        Evidence.model_validate(invalid)
    invalid = copy.deepcopy(data)
    invalid["audits"][-1]["status"] = "located"
    with pytest.raises(ValidationError, match="unreviewed"):
        Evidence.model_validate(invalid)


@pytest.mark.parametrize(
    "field,value",
    [("value", "NaN"), ("value", "-1"), ("value", 20), ("upper_bound", "50"), ("unit", "GWh"), ("page", 3)],
)
def test_reject_invalid_observation(field, value):
    data = synthetic()
    data["observations"][0][field] = value
    with pytest.raises(ValidationError):
        Evidence.model_validate(data)


def test_scopes_groups_rest_and_names_remain_separate(tmp_path):
    data = synthetic()
    for kind in ("group", "rest", "total"):
        data["entities"].append(dict(data["entities"][0], gas_id=f"gas-{kind}", kind=kind))
        data["mappings"].append(
            dict(data["mappings"][0], mapping_id=f"map-{kind}", gas_id=f"gas-{kind}", observed_name=f"Synthetic {kind}")
        )
        data["observations"].append(
            dict(data["observations"][2], observation_id=f"obs-{kind}", mapping_id=f"map-{kind}")
        )
    data["observations"].append(dict(data["observations"][2], observation_id="liberalised", scope="liberalised"))
    evidence = Evidence.model_validate(data)
    database = tmp_path / "test.sqlite"
    ingest(evidence, database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM gas_retail_quarters").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(DISTINCT kind) FROM gas_retail_entities").fetchone()[0] == 4
        assert connection.execute("SELECT COUNT(DISTINCT scope) FROM gas_retail_quarters").fetchone()[0] == 2
        assert (
            connection.execute("SELECT observed_name FROM gas_retail_mappings WHERE gas_id='gas-test'").fetchone()[0]
            == "Test name"
        )


def test_immutable_revisions_idempotence_and_corruption_detection(tmp_path):
    database = tmp_path / "test.sqlite"
    evidence = Evidence.model_validate(synthetic())
    first = ingest(evidence, database)
    assert ingest(evidence, database) == first
    data = synthetic()
    data["observations"][2]["value"] = "31"
    second = ingest(Evidence.model_validate(data), database)
    assert first != second
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM gas_retail_loads").fetchone()[0] == 2
        assert verify_load(connection, evidence)["gas_retail_observations"] == 6
        connection.execute("UPDATE gas_retail_observations SET value='999' WHERE load_id=?", (first,))
    with pytest.raises(ValueError, match="immutable"):
        ingest(evidence, database)


def test_transaction_rolls_back_schema_and_load_on_failure(tmp_path, monkeypatch):
    from electricity_map_ingestion import gas_retail_store

    original = gas_retail_store.write_load

    def fail(connection, evidence):
        original(connection, evidence)
        raise ValueError("Injected persistence failure")

    monkeypatch.setattr(gas_retail_store, "write_load", fail)
    database = tmp_path / "rollback.sqlite"
    with pytest.raises(ValueError, match="Injected"):
        ingest(Evidence.model_validate(synthetic()), database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name LIKE 'gas_retail_%'").fetchall() == []


def test_repeated_source_rows_survive_without_double_counting(tmp_path):
    data = synthetic()
    data["observations"].append(dict(data["observations"][2], observation_id="repeated-source-row", source_row="2"))
    evidence = Evidence.model_validate(data)
    database = tmp_path / "repeated.sqlite"
    ingest(evidence, database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM gas_retail_observations").fetchone()[0] == 7
        assert connection.execute(
            "SELECT status, value FROM gas_retail_quarters WHERE metric='clients'"
        ).fetchone() == ("source_error", None)


def test_source_and_json_validation_before_decode(tmp_path):
    path = tmp_path / "input.json"
    for payload in (b"<html>error", b'{"x":' + b"[" * 20 + b"0" + b"]" * 20 + b"}", b'{"x":1,"x":2}'):
        path.write_bytes(payload)
        with pytest.raises(ValueError):
            read_evidence(path)
    data = synthetic()
    path.write_text(json.dumps(data))
    assert read_evidence(path).version == 1
    body = b"%PDF-1.4\n" + b" " * 100 + b"\n%%EOF\n"
    source = tmp_path / "synthetic.pdf"
    source.write_bytes(body)
    data["sources"][0].update(byte_size=len(body), sha256=hashlib.sha256(body).hexdigest())
    verify_sources(Evidence.model_validate(data), tmp_path)
    source.write_bytes(body.replace(b"PDF", b"BAD"))
    data["sources"][0]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="signature"):
        verify_sources(Evidence.model_validate(data), tmp_path)


def test_export_is_local_additive_and_verified(tmp_path):
    database = tmp_path / "test.sqlite"
    evidence = Evidence.model_validate(synthetic())
    load_id = ingest(evidence, database)
    counts = export(database, load_id)
    assert counts["gas_retail_audits"] == 180
    destination = tmp_path / "export"
    assert export(database, load_id, destination) == counts
    schema = (destination / "schema.sql").read_text()
    sql = (destination / "data.sql").read_text()
    assert all(table in schema for table in TABLES)
    assert "DROP TABLE" not in schema and "DELETE" not in sql and "UPDATE" not in sql
    assert "CHECK (ok)" in sql and "EXCEPT ALL" in sql and "ON CONFLICT DO NOTHING" in sql
    assert sql.count("FROM STDIN;") == len(TABLES)
    assert sql.count("\\.\n") == len(TABLES)
    assert "\\echo Carga masiva confirmada." in sql
    assert literal("O'Brien\\path") == "'O''Brien\\path'"
    with pytest.raises(FileExistsError):
        export(database, load_id, destination)
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM gas_retail_observations WHERE observation_id='obs-sales-1'")
    with pytest.raises(ValueError, match="immutable"):
        export(database, load_id)


def test_copy_text_distinguishes_null_empty_and_escaped_values():
    assert copy_field(None) == r"\N"
    assert copy_field(0) == "0"
    assert copy_field("") == ""
    assert copy_field(r"\N") == r"\\N"
    assert copy_field(r"\.") == r"\\."
    assert copy_field("O'Brien\tá\nline\r\\path") == "O'Brien\\tá\\nline\\r\\\\path"
    with pytest.raises(ValueError, match="NUL"):
        copy_field("bad\x00text")


def test_postgres_roundtrip_and_conflict_guard(tmp_path):
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set TEST_POSTGRES_URL to an isolated PostgreSQL service")
    import psycopg
    from sqlalchemy.engine import make_url

    parsed = make_url(url)
    if parsed.host not in {"localhost", "127.0.0.1", "::1", "postgres"}:
        pytest.skip("Gas retail integration test requires a local isolated service")
    assert shutil.which("psql"), "Install the PostgreSQL client to test the actual COPY import"
    database = tmp_path / "test.sqlite"
    data = synthetic()
    data["sources"][0]["notes"] = "O'Brien\tá\n\\.\r\\N\\path"
    evidence = Evidence.model_validate(data)
    load_id = ingest(evidence, database)
    destination = tmp_path / "export"
    counts = export(database, load_id, destination)
    schema_name = "test_gas_retail_" + uuid4().hex
    dsn = parsed.set(drivername="postgresql").render_as_string(hide_password=False)

    def run_import(sql):
        return subprocess.run(
            ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1"],
            input=sql,
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "PGHOST": parsed.host,
                "PGPORT": str(parsed.port or 5432),
                "PGDATABASE": parsed.database,
                "PGUSER": parsed.username or "postgres",
                "PGPASSWORD": parsed.password or "",
                "PGCLIENTENCODING": "UTF8",
            },
            timeout=60,
        )

    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema_name}"')
        try:
            schema = (
                (destination / "schema.sql")
                .read_text()
                .replace("search_path = public", f'search_path = "{schema_name}"')
            )
            sql = (
                (destination / "data.sql").read_text().replace("search_path = public", f'search_path = "{schema_name}"')
            )
            connection.execute(schema, prepare=False)
            first = run_import(sql)
            assert first.returncode == 0, first.stderr
            connection.execute(f"UPDATE \"{schema_name}\".gas_retail_loads SET imported_at='first-import'")
            repeat = run_import(sql)
            assert repeat.returncode == 0, repeat.stderr
            assert (
                connection.execute(f'SELECT imported_at FROM "{schema_name}".gas_retail_loads').fetchone()[0]
                == "first-import"
            )
            assert (
                connection.execute(f'SELECT notes FROM "{schema_name}".gas_retail_sources').fetchone()[0]
                == data["sources"][0]["notes"]
            )
            for table, count in counts.items():
                assert connection.execute(f'SELECT COUNT(*) FROM "{schema_name}".{table}').fetchone()[0] == count
            connection.execute(f"UPDATE \"{schema_name}\".gas_retail_quarters SET value='999'")
            # Earlier tables would insert this absent row, but a later conflict must roll it back.
            connection.execute(f'DELETE FROM "{schema_name}".gas_retail_audits')
            conflict = run_import(sql)
            assert conflict.returncode != 0
            assert "check constraint" in conflict.stderr
            assert "Carga masiva confirmada." not in conflict.stdout
            assert connection.execute(f'SELECT COUNT(*) FROM "{schema_name}".gas_retail_audits').fetchone()[0] == 0
            assert revision_id(evidence) == load_id
        finally:
            connection.execute(f'DROP SCHEMA "{schema_name}" CASCADE')

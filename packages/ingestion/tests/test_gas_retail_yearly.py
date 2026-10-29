"""Yearly review imports preserve source distinctions and migrate transactionally."""

import csv
import hashlib
import json
import sqlite3

import pytest
from electricity_map_ingestion import gas_retail_store as store
from electricity_map_ingestion.gas_retail import Evidence, ingest
from electricity_map_ingestion.gas_retail_yearly import (
    ALIASES,
    AUDIT,
    IDENTITY_SOURCES,
    INVENTORY,
    MONTHLY,
    QUARTERLY,
    prepare,
    read_csv,
)
from test_gas_retail import synthetic


def reviewed():
    data = synthetic()
    data.update(version=2, source_audits=[], unresolved_observations=[], observation_details=[], review_records=[])
    for audit in data["audits"]:
        audit["source_ids"] = ["synthetic"]
        data["source_audits"].append(
            dict(
                audit,
                source_id="synthetic",
                table_review_status=audit["status"],
                retailer_coverage="reviewed" if audit["status"] == "reviewed" else "unknown",
                geographic_scope="Synthetic geography",
            )
        )
    for row in data["observations"]:
        data["observation_details"].append(
            dict(observation_id=row["observation_id"], original_unit=row["unit"], review_status="reviewed")
        )
    return data


def test_version_one_hash_and_revision_are_preserved():
    data = synthetic()
    expected = hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    assert store.revision_id(Evidence.model_validate(data)) == expected


def test_source_conflict_note_is_preserved_with_bounded_length(tmp_path):
    data = reviewed()
    note = "Conflicting totals in the source; retain both printed references. " * 20
    data["observations"][0]["review_note"] = note
    evidence = Evidence.model_validate(data)
    database = tmp_path / "notes.sqlite"
    load_id = ingest(evidence, database)
    with sqlite3.connect(database) as connection:
        stored = connection.execute(
            "SELECT review_note FROM gas_retail_observations WHERE load_id=? AND observation_id=?",
            (load_id, data["observations"][0]["observation_id"]),
        ).fetchone()[0]
    assert stored == note
    data["observations"][0]["review_note"] = "x" * 4001
    with pytest.raises(ValueError, match="4000"):
        Evidence.model_validate(data)


def test_source_audits_cannot_promote_alternatives():
    data = reviewed()
    data["source_audits"][-1]["retailer_coverage"] = "partial"
    with pytest.raises(ValueError, match="promote"):
        Evidence.model_validate(data)


def test_unresolved_month_is_preserved_without_inventing_june(tmp_path):
    data = reviewed()
    row = data["observations"].pop()
    for key in ("month", "value", "upper_bound"):
        row.pop(key)
    data["unresolved_observations"].append(dict(row, period="2026T1", status="source_error"))
    evidence = Evidence.model_validate(data)
    database = tmp_path / "review.sqlite"
    load_id = ingest(evidence, database)
    assert ingest(evidence, database) == load_id
    with sqlite3.connect(database) as connection:
        assert store.verify_load(connection, evidence)["gas_retail_unresolved_observations"] == 1
        sales = connection.execute(
            "SELECT status,value,missing_months_json,observation_ids_json FROM gas_retail_quarters WHERE metric='sales'"
        ).fetchone()
        clients = connection.execute(
            "SELECT observation_ids_json FROM gas_retail_quarters WHERE metric='clients'"
        ).fetchone()
    assert sales[:3] == ("missing", None, '["2026-03"]')
    assert row["observation_id"] in json.loads(sales[3])
    assert json.loads(clients[0]) == ["obs-clients-3"]


def legacy_database(path):
    original = Evidence.model_validate(synthetic())
    ddl = (
        store.schema_sql()
        .replace("'total', 'direct_consumer', 'unknown'", "'total'")
        .replace("UNIQUE (load_id, source_id, observed_name, gas_id)", "UNIQUE (load_id, source_id, observed_name)")
    )
    with sqlite3.connect(path) as connection:
        connection.executescript(ddl)
        store.write_load(connection, original)
    return original


def test_migration_preserves_revisions_and_same_label_distinct_kinds(tmp_path):
    path = tmp_path / "old.sqlite"
    original = legacy_database(path)
    data = reviewed()
    data["entities"].append(dict(data["entities"][0], gas_id="gas-unknown", kind="unknown"))
    data["mappings"].append(dict(data["mappings"][0], mapping_id="map-unknown", gas_id="gas-unknown"))
    updated = Evidence.model_validate(data)
    ingest(updated, path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert not store.needs_entity_migration(connection)
        store.verify_load(connection, original)
        store.verify_load(connection, updated)
        assert connection.execute("SELECT COUNT(*) FROM gas_retail_loads").fetchone()[0] == 2


def test_failed_migration_rolls_back_ddl_and_rows(tmp_path, monkeypatch):
    path = tmp_path / "old.sqlite"
    original = legacy_database(path)

    def fail(*args):
        raise ValueError("Injected failure")

    monkeypatch.setattr(store, "write_load", fail)
    with pytest.raises(ValueError, match="Injected"):
        ingest(Evidence.model_validate(reviewed()), path)
    with sqlite3.connect(path) as connection:
        assert store.needs_entity_migration(connection)
        store.verify_load(connection, original)


def csv_file(directory, name, fields, rows):
    with (directory / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict.fromkeys(fields, "") | row)


def review_files(directory):
    data = reviewed()
    base = Evidence.model_validate(synthetic())
    source = base.sources[0]
    provenance = dict(
        source_id=source.source_id,
        source_url=source.url,
        source_sha256=source.sha256,
        publication_date=source.published_on,
    )
    csv_file(
        directory,
        "source_inventory.csv",
        INVENTORY,
        [
            dict(
                provenance,
                file_name=source.file_name,
                byte_size=source.byte_size,
                pages=source.page_count,
                reporting_year="2026",
                reporting_periods="2026T1",
                title=source.title,
                validation_status="validated",
                copy_allowed="true",
                encrypted="false",
                reuse_status="review_pending",
            )
        ],
    )
    csv_file(directory, "identity_sources.csv", IDENTITY_SOURCES, [])
    csv_file(
        directory,
        "company_aliases.csv",
        ALIASES,
        [
            dict(
                {k: v for k, v in provenance.items() if k != "publication_date"},
                company_id="gas-test",
                company_name="Synthetic company",
                observed_name="Test name",
                entity_kind="retailer",
                pdf_page="1",
                identity_review_status="source_local_identity",
                supporting_evidence="[]",
                notes="Synthetic identity",
            )
        ],
    )
    csv_file(directory, "identity_events.csv", "event_id company_id company_name decision evidence".split(), [])
    csv_file(directory, "unresolved_issues.csv", "issue_id source_id period metric issue details".split(), [])
    for year in range(2003, 2027):
        audits = [
            dict(
                provenance,
                year=str(year),
                quarter=r["period"][-1],
                metric=r["metric"],
                source_title=source.title,
                pdf_pages="1",
                market_scope="whole_market",
                original_unit="clients" if r["metric"] == "clients" else "MWh",
                review_status=r["status"],
                table_review_status=r["table_review_status"],
                retailer_coverage=r["retailer_coverage"],
                monthly_observations="3" if year == 2026 else "0",
                quarterly_observations="1" if year == 2026 else "0",
                geographic_scope=r["geographic_scope"],
                notes="Synthetic audit",
            )
            for r in data["source_audits"]
            if r["period"].startswith(str(year))
        ]
        common = dict(
            provenance,
            company_id="gas-test",
            company_name="Synthetic company",
            observed_name="Test name",
            entity_kind="retailer",
            year=str(year),
            quarter="1",
            market_scope="whole_market",
            review_status="reviewed",
            notes="Synthetic notes",
            table_label="Synthetic table",
        )
        monthly = (
            [
                dict(
                    common,
                    month=r["month"],
                    metric=r["metric"],
                    raw_value=r["raw_value"],
                    value=r["value"],
                    value_status="exact",
                    original_unit=r["unit"],
                    value_mwh=r["value"] if r["metric"] == "sales" else "",
                    pdf_page="1",
                    source_row="1",
                    observation_id=r["observation_id"],
                )
                for r in data["observations"]
            ]
            if year == 2026
            else []
        )
        quarters = (
            [
                dict(
                    common,
                    metric=metric,
                    value="30" if metric == "clients" else "60",
                    value_status="exact",
                    original_unit="clients" if metric == "clients" else "MWh",
                    value_mwh="" if metric == "clients" else "60",
                    pdf_pages="1",
                    source_rows="1",
                    observation_ids="obs-clients-3" if metric == "clients" else "obs-sales-1;obs-sales-2;obs-sales-3",
                    months="2026-03" if metric == "clients" else "2026-01;2026-02;2026-03",
                )
                for metric in ("clients", "sales")
            ]
            if year == 2026
            else []
        )
        csv_file(directory, f"gas_{year}_monthly.csv", MONTHLY, monthly)
        csv_file(directory, f"gas_{year}_quarterly.csv", QUARTERLY, quarters)
        csv_file(directory, f"gas_{year}_audit.csv", AUDIT, audits)
    # The independent catalogue must use a distinct identity from statistics.
    data = base.model_dump()
    data["catalogue"] = []
    return Evidence.model_validate(data)


def test_csv_bundle_recalculates_quarters_and_rejects_modified_results(tmp_path):
    base = review_files(tmp_path)
    evidence, report = prepare(tmp_path, base)
    assert report["quarterly"] == 2 and len(evidence.source_audits) == 180
    path = tmp_path / "gas_2026_quarterly.csv"
    rows, _ = read_csv(path, QUARTERLY)
    rows[1]["value"] = "999"
    rows[1]["value_mwh"] = "999"
    csv_file(tmp_path, path.name, QUARTERLY, rows)
    with pytest.raises(ValueError, match="Quarter mismatch"):
        prepare(tmp_path, base)


def test_partial_cell_cannot_inherit_reviewed_period():
    data = reviewed()
    data["observation_details"][0]["review_status"] = "partial"
    with pytest.raises(ValueError, match="unreviewed cell"):
        Evidence.model_validate(data)


@pytest.mark.parametrize("content", [b"a,b\n1\x00,2", b"a,b\n1,2,3", b"b,a\n1,2", b"a,b\n\xff,2"])
def test_csv_validation_rejects_invalid_inputs(tmp_path, content):
    path = tmp_path / "input.csv"
    path.write_bytes(content)
    with pytest.raises((ValueError, UnicodeDecodeError)):
        read_csv(path, ["a", "b"])

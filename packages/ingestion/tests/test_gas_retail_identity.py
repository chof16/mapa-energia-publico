"""Cross-report identities preserve observed names, rows and immutable revisions."""

import json
import sqlite3

import pytest
from electricity_map_ingestion.gas_retail import Evidence, ingest, require_company_identities
from electricity_map_ingestion.gas_retail_identity import IdentityRegistry, reconcile
from electricity_map_ingestion.gas_retail_store import revision_id
from test_gas_retail import synthetic


def evidence_and_registry():
    data = synthetic()
    data["catalogue"] = []
    data["sources"].append(dict(data["sources"][0], source_id="previous"))
    data["entities"].append(dict(data["entities"][0], gas_id="gas-previous"))
    data["mappings"].append(
        dict(
            data["mappings"][0],
            mapping_id="map-previous",
            source_id="previous",
            observed_name="Previous company name",
            gas_id="gas-previous",
        )
    )
    for audit in data["audits"]:
        if audit["period"] == "2025T4":
            audit.update(status="reviewed", source_ids=["previous"], pages=[1])
    data["observations"] += [
        dict(
            row,
            observation_id=row["observation_id"] + "-previous",
            source_id="previous",
            mapping_id="map-previous",
            month=f"2025-{int(row['month'][-2:]) + 9}",
        )
        for row in list(data["observations"])
    ]
    evidence = Evidence.model_validate(data)
    registry = dict(
        version=1,
        base_load_id=revision_id(evidence),
        decisions=[
            dict(
                entity=dict(
                    data["entities"][0],
                    gas_id="gas-stable",
                    review_note="reviewed_identity: Explicit synthetic cross-report identity review.",
                ),
                mapping_ids=["map-test", "map-previous"],
                references=[dict(source_id="synthetic", page=1)],
            )
        ],
    )
    return evidence, registry


def test_stable_identity_across_documents_preserves_all_observations(tmp_path):
    evidence, registry = evidence_and_registry()
    result = reconcile(evidence, IdentityRegistry.model_validate(registry))
    assert len(result.entities) == 1
    assert {row.gas_id for row in result.mappings} == {"gas-stable"}
    assert {row.observed_name for row in result.mappings} == {"Test name", "Previous company name"}
    assert result.observations == evidence.observations and result.audits == evidence.audits
    database = tmp_path / "gas.sqlite"
    old = ingest(evidence, database)
    new = ingest(result, database)
    assert old != new and ingest(result, database) == new
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM gas_retail_loads").fetchone()[0] == 2
        rows = connection.execute(
            "SELECT DISTINCT gas_id,period FROM gas_retail_quarters WHERE load_id=? ORDER BY period", (new,)
        ).fetchall()
    assert rows == [("gas-stable", "2025T4"), ("gas-stable", "2026T1")]


@pytest.mark.parametrize("problem", ["revision", "incomplete", "duplicate", "kind", "reference"])
def test_identity_registry_rejects_ambiguous_or_unreviewed_changes(problem):
    evidence, registry = evidence_and_registry()
    decision = registry["decisions"][0]
    if problem == "revision":
        registry["base_load_id"] = "0" * 64
    elif problem == "incomplete":
        decision["mapping_ids"].pop()
    elif problem == "duplicate":
        decision["mapping_ids"].append("map-test")
    elif problem == "kind":
        decision["entity"]["kind"] = "group"
    else:
        decision["references"][0]["page"] = 100
    with pytest.raises(ValueError):
        reconcile(evidence, IdentityRegistry.model_validate(registry))


def test_identity_merge_cannot_combine_coexisting_companies():
    evidence, registry = evidence_and_registry()
    data = evidence.model_dump()
    data["mappings"][1]["source_id"] = "synthetic"
    for row in data["observations"]:
        if row["mapping_id"] == "map-previous":
            row.update(source_id="synthetic", month=f"2026-{int(row['month'][-2:]) - 9:02}")
    changed = Evidence.model_validate(data)
    registry["base_load_id"] = revision_id(changed)
    with pytest.raises(ValueError, match="coexisting"):
        reconcile(changed, IdentityRegistry.model_validate(registry))


def test_work_review_cells_and_audits_survive_company_identity_resolution(tmp_path):
    evidence, registry = evidence_and_registry()
    data = evidence.model_dump()
    data["version"] = 2
    data["source_audits"] = []
    for audit in data["audits"]:
        if not audit["source_ids"]:
            audit["source_ids"] = ["synthetic"]
        data["source_audits"].append(
            dict(
                audit,
                source_id=audit["source_ids"][0],
                table_review_status=audit["status"],
                retailer_coverage="reviewed" if audit["status"] == "reviewed" else "unknown",
                geographic_scope="Synthetic source geography",
            )
        )
    data["observation_details"] = [
        dict(observation_id=row["observation_id"], original_unit=row["unit"], review_status="reviewed")
        for row in data["observations"]
    ]
    evidence = Evidence.model_validate(data)
    registry["base_load_id"] = revision_id(evidence)
    unmarked = IdentityRegistry.model_validate(registry).model_dump()
    unmarked["decisions"][0]["entity"]["review_note"] = "Missing explicit admission"
    with pytest.raises(ValueError, match="reviewed_identity"):
        reconcile(evidence, IdentityRegistry.model_validate(unmarked))
    result = reconcile(evidence, IdentityRegistry.model_validate(registry))
    assert result.entities[0].review_note.startswith("reviewed_identity:")
    for field in ("observations", "source_audits", "audits", "observation_details", "sources"):
        assert getattr(result, field) == getattr(evidence, field)
    recorded = json.loads(result.review_records[-1].payload_json)
    assert recorded["base_load_id"] == revision_id(evidence)
    assert recorded["decision"]["entity"]["gas_id"] == "gas-stable"
    database = tmp_path / "companies.sqlite"
    load_id = ingest(result, database)
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(DISTINCT gas_id),COUNT(DISTINCT source_id),COUNT(DISTINCT period) "
            "FROM gas_retail_quarters WHERE load_id=?",
            (load_id,),
        ).fetchone()
    assert rows == (1, 2, 2)


def test_source_local_extraction_ids_cannot_be_imported_as_companies(tmp_path):
    from test_gas_retail_yearly import reviewed

    data = reviewed()
    data["catalogue"] = []
    data["entities"][0]["gas_id"] = "gas-cnmc-source-company"
    data["mappings"][0]["gas_id"] = "gas-cnmc-source-company"
    evidence = Evidence.model_validate(data)
    with pytest.raises(ValueError, match="--identities"):
        require_company_identities(evidence)
    database = tmp_path / "blocked.sqlite"
    with pytest.raises(ValueError, match="--identities"):
        ingest(evidence, database)
    assert not database.exists()

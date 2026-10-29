"""Synthetic public gas contracts: reviewed values, provenance and honest gaps."""

import os
import sqlite3
from dataclasses import replace
from uuid import uuid4

import pytest
from electricity_map_api.cache import RedisResponseCache
from electricity_map_api.config import Settings
from electricity_map_api.main import create_app
from electricity_map_ingestion.gas_retail import Evidence, ingest, periods
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from scripts.export_database import _ordered_dump

BASE = "/v1/gas/retail"


def evidence_data():
    source = dict(
        source_id="report",
        url="https://www.cnmc.es/synthetic.pdf",
        title="Synthetic report",
        publisher="CNMC",
        published_on=None,
        retrieved_on="2026-10-29",
        sha256="a" * 64,
        file_name="synthetic.pdf",
        media_type="pdf",
        byte_size=100,
        page_count=5,
        reuse_status="review_pending",
        notes="Synthetic peninsular scope; no national inference.",
    )
    entities, mappings, observations = [], [], []
    for name, kind in (("test", "retailer"), ("total", "total"), ("group", "group"), ("rest", "rest")):
        entities.append(
            dict(gas_id=f"gas-{name}", name=f"Entity {name}", kind=kind, review_note="Synthetic identity only.")
        )
        mappings.append(
            dict(
                mapping_id=f"map-{name}",
                source_id="report",
                observed_name=f"Observed {name}",
                gas_id=f"gas-{name}",
                review_note="Literal synthetic mapping.",
            )
        )
        for metric in ("clients", "sales"):
            for month in (1, 2, 3):
                value = str(month * (100 if kind == "total" else 10))
                observations.append(
                    dict(
                        observation_id=f"{name}-{metric}-{month}",
                        source_id="report",
                        mapping_id=f"map-{name}",
                        month=f"2026-{month:02}",
                        metric=metric,
                        scope="whole_market",
                        unit="clients" if metric == "clients" else "GWh",
                        page=2,
                        table_label="Monthly evidence",
                        source_row=name,
                        raw_value=value,
                        status="exact",
                        value=value,
                        upper_bound=None,
                        review_note="Synthetic reviewed observation.",
                    )
                )
    observations.append(
        dict(observations[2], observation_id="partial-cell", month="2025-12", value="999", raw_value="999")
    )
    catalogue = []
    for index in range(4):
        gas_id = f"gas-cur-{index}"
        entities.append(
            dict(gas_id=gas_id, name=f"CUR {index}", kind="retailer", review_note="Independent catalogue ID.")
        )
        for source_id, date in (("guide", "2022-11-14"), ("page", "2026-10-29")):
            catalogue.append(
                dict(
                    gas_id=gas_id,
                    observed_name=f"CUR {index} variant {source_id}",
                    designation="gas_cur",
                    source_id=source_id,
                    page=3 if source_id == "guide" else 0,
                    evidence_on=date,
                    review_note="Source observation, not designation start date.",
                )
            )
    return dict(
        version=1,
        reviewed_on="2026-10-29",
        complete=False,
        sources=[
            source,
            dict(source, source_id="guide", sha256="b" * 64),
            dict(
                source, source_id="page", sha256="c" * 64, media_type="html", page_count=0, file_name="synthetic.html"
            ),
        ],
        entities=entities,
        mappings=mappings,
        observations=observations,
        catalogue=catalogue,
        audits=[
            dict(
                period=period,
                metric=metric,
                status="reviewed" if period == "2026T1" else "partial" if period == "2025T4" else "not_reviewed",
                source_ids=["report"] if period in {"2025T4", "2026T1"} else [],
                pages=[2] if period in {"2025T4", "2026T1"} else [],
                note="Synthetic independent metric audit.",
            )
            for period in periods()
            for metric in ("clients", "sales")
        ],
    )


@pytest.fixture
def retail_database(tmp_path):
    path = tmp_path / "retail.sqlite"
    ingest(Evidence.model_validate(evidence_data()), path)
    return path


def continuity_data():
    """One explicitly reviewed company identity with distinct report aliases."""
    data = evidence_data()
    data["entities"][0]["name"] = "Canonical renamed supplier"
    current = [row.copy() for row in data["observations"] if row["month"].startswith("2026")]
    for source_id, period, month_start, alias in (
        ("earlier", "2024T4", 10, "Earlier alias"),
        ("middle", "2025T3", 7, "Middle alias"),
    ):
        data["sources"].append(dict(data["sources"][0], source_id=source_id))
        for mapping in data["mappings"][:2]:
            data["mappings"].append(
                dict(
                    mapping,
                    mapping_id=f"{mapping['mapping_id']}-{source_id}",
                    source_id=source_id,
                    observed_name=alias if mapping["gas_id"] == "gas-test" else f"Total {source_id}",
                )
            )
        for row in current:
            if row["mapping_id"] not in {"map-test", "map-total"}:
                continue
            observation = dict(
                row,
                observation_id=f"{row['observation_id']}-{source_id}",
                source_id=source_id,
                mapping_id=f"{row['mapping_id']}-{source_id}",
                month=f"{period[:4]}-{month_start + int(row['month'][-2:]) - 1:02}",
            )
            data["observations"].append(observation)
            if source_id == "middle" and row["mapping_id"] == "map-test":
                data["observations"].append(
                    dict(
                        observation,
                        observation_id=observation["observation_id"] + "-lib",
                        scope="liberalised",
                    )
                )
        for audit in data["audits"]:
            if audit["period"] == period:
                audit.update(status="reviewed", source_ids=[source_id], pages=[2])
    data["mappings"].append(dict(data["mappings"][0], mapping_id="map-private", observed_name="Private alias"))
    next(row for row in data["observations"] if row["observation_id"] == "partial-cell")["mapping_id"] = "map-private"
    data["entities"].append(dict(data["entities"][0], gas_id="gas-other", name="Other supplier"))
    data["mappings"].append(
        dict(data["mappings"][0], mapping_id="map-other", gas_id="gas-other", observed_name="Other observed")
    )
    data["observations"].append(dict(current[2], observation_id="other-cell", mapping_id="map-other"))
    return data


def work_data(data=None):
    """Synthetic v2 review with explicit source audits and original cell units."""
    data = data or continuity_data()
    data.update(version=2, source_audits=[], observation_details=[], unresolved_observations=[], review_records=[])
    data["entities"][0]["review_note"] = "reviewed_identity: Explicit synthetic continuity decision."
    for entity in data["entities"][1:]:
        entity["review_note"] = "source_local_identity: No cross-report identity evidence."
    for audit in data["audits"]:
        audit["source_ids"] = audit["source_ids"] or ["report"]
        for source_id in audit["source_ids"]:
            data["source_audits"].append(
                dict(
                    audit,
                    source_id=source_id,
                    source_ids=[source_id],
                    table_review_status=audit["status"],
                    retailer_coverage="reviewed" if audit["status"] == "reviewed" else "partial",
                    geographic_scope="Synthetic source geography, not inferred nationwide.",
                )
            )
    for row in data["observations"]:
        data["observation_details"].append(
            dict(
                observation_id=row["observation_id"],
                original_unit="Número de Clientes" if row["metric"] == "clients" else row["unit"],
                review_status="partial" if row["observation_id"] == "partial-cell" else "reviewed",
            )
        )
    return data


def add_partial_alternative(data):
    data["sources"].append(dict(data["sources"][0], source_id="alternative"))
    data["mappings"].append(
        dict(
            data["mappings"][0],
            source_id="alternative",
            mapping_id="map-alternative",
            observed_name="Private alternative alias",
        )
    )
    data["observations"].append(
        dict(
            data["observations"][2],
            source_id="alternative",
            mapping_id="map-alternative",
            observation_id="alternative-cell",
            value="987654321",
            raw_value="987654321",
        )
    )
    data["observation_details"].append(
        dict(
            observation_id="alternative-cell",
            original_unit="Clientes",
            review_status="partial",
        )
    )
    audit = next(row for row in data["audits"] if row["period"] == "2026T1" and row["metric"] == "clients")
    audit.update(status="partial", source_ids=["report", "alternative"])
    data["source_audits"].append(
        dict(
            audit,
            source_id="alternative",
            source_ids=["alternative"],
            table_review_status="partial",
            retailer_coverage="partial",
            geographic_scope="Alternative geography",
        )
    )


def test_v2_source_audit_exposes_reviewed_alternative_without_partial_leak(tmp_path):
    data = work_data()
    add_partial_alternative(data)
    path = tmp_path / "alternatives.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        periods_body = client.get(BASE + "/periods?period=2026T1").json()["items"][0]
        assert periods_body["audit"]["status"] == "partial"
        assert periods_body["reviewed_retailer_count"] == 1
        assert {audit["status"] for audit in periods_body["source_audits"]} == {"reviewed", "partial"}
        marketers_body = client.get(BASE + "/marketers?period=2026T1").json()
        assert marketers_body["total"] == 1
        assert client.get(BASE + "/marketers?search=Private%20alternative").json()["items"] == []
        body = client.get(BASE + "/series/gas-test?start_period=2026T1").json()
        point = body["items"][0]
        assert point["audit"]["status"] == "partial" and point["availability"] == "reviewed"
        assert len(point["source_audits"]) == 2 and len(point["records"]) == 1
        value = point["records"][0]
        assert value["value"] == "30" and value["review_status"] == "reviewed"
        assert value["source_audit"]["source"]["source_id"] == "report"
        assert value["observations"][0]["original_unit"] == "Número de Clientes"
        assert value["observations"][0]["review_status"] == "reviewed"
        assert len(value["observations"]) == 1  # v2 clients reference only the final month.
        assert "987654321" not in str(body) and "Private alternative alias" not in str(body)


def test_v2_partial_cell_blocks_aggregate_and_redacts_literal(tmp_path):
    data = work_data()
    target = next(row for row in data["observations"] if row["observation_id"] == "test-sales-3")
    target.update(value="987654321", raw_value="987654321")
    next(row for row in data["observation_details"] if row["observation_id"] == target["observation_id"])[
        "review_status"
    ] = "partial"
    next(row for row in data["audits"] if row["period"] == "2026T1" and row["metric"] == "sales")["status"] = "partial"
    path = tmp_path / "partial-cell.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        value = series(client, "&metric=sales")
        assert value["review_status"] == "partial" and value["status"] == "missing"
        assert value["value"] is None and value["original_value"] is None and value["share"] is None
        assert value["withheld_observation_ids"] == ["test-sales-3"]
        assert len(value["observations"]) == 2 and "987654321" not in str(value)


@pytest.mark.parametrize("target", ["test-clients-1", "total-clients-3"])
def test_v2_clients_use_only_final_month_and_deny_partial_denominator(tmp_path, target):
    data = work_data()
    next(row for row in data["observation_details"] if row["observation_id"] == target)["review_status"] = "partial"
    next(row for row in data["audits"] if row["period"] == "2026T1" and row["metric"] == "clients")["status"] = (
        "partial"
    )
    path = tmp_path / "client-review.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        value = series(client)
        assert value["review_status"] == "reviewed" and value["value"] == "30"
        assert [row["observation_id"] for row in value["observations"]] == ["test-clients-3"]
        if target.startswith("total"):
            assert value["share"] is None and value["denominator_status"] == "unavailable"
            assert value["denominator"]["value"] is None and value["denominator"]["original_value"] is None
        else:
            assert value["share"] == "0.1"


def test_v2_unresolved_month_preserves_error_provenance_without_numbers(tmp_path):
    data = work_data()
    unresolved = next(row for row in data["observations"] if row["observation_id"] == "test-sales-3")
    data["observations"].remove(unresolved)
    for key in ("month", "value", "upper_bound"):
        unresolved.pop(key)
    unresolved.update(period="2026T1", status="source_error", review_note="Unresolved printed month Juio.")
    data["unresolved_observations"].append(unresolved)
    for audit in data["audits"]:
        if audit["period"] == "2026T1" and audit["metric"] == "sales":
            audit["status"] = "source_error"
    for audit in data["source_audits"]:
        if audit["period"] == "2026T1" and audit["metric"] == "sales":
            audit.update(status="source_error", table_review_status="source_error", retailer_coverage="partial")
    for detail in data["observation_details"]:
        if detail["observation_id"] in {"test-sales-1", "test-sales-2", "test-sales-3"}:
            detail["review_status"] = "source_error"
    path = tmp_path / "unresolved.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        assert client.get(BASE + "/marketers?metric=sales&period=2026T1").json()["total"] == 1
        point = client.get(BASE + "/series/gas-test?metric=sales&start_period=2026T1").json()["items"][0]
        assert point["availability"] == "unavailable"
        value = point["records"][0]
        assert value["status"] == "missing" and value["missing_months"] == ["2026-03"]
        assert value["review_status"] == "source_error" and value["value"] is None
        assert value["original_value"] is None and value["share"] is None
        cell = value["unresolved_observations"][0]
        assert cell["month"] is None and cell["period"] == "2026T1"
        assert cell["raw_value"] == "30" and cell["value"] is None
        assert cell["review_status"] == "source_error" and cell["original_unit"] == "GWh"
        assert all(
            row["value"] is None and row["publication_status"] == "source_error" for row in value["observations"]
        )


def test_v2_identity_status_and_same_label_entity_kinds_remain_separate(tmp_path):
    data = work_data()
    next(row for row in data["entities"] if row["gas_id"] == "gas-other")["name"] = data["entities"][0]["name"]
    for kind in ("group", "direct_consumer", "unknown"):
        gas_id = f"gas-new-{kind.replace('_', '-')}"
        data["entities"].append(dict(data["entities"][0], gas_id=gas_id, kind=kind))
        mapping_id = f"map-new-{kind}"
        data["mappings"].append(dict(data["mappings"][0], gas_id=gas_id, mapping_id=mapping_id))
        row = dict(data["observations"][2], observation_id=f"new-{kind}", mapping_id=mapping_id)
        data["observations"].append(row)
        data["observation_details"].append(
            dict(observation_id=row["observation_id"], original_unit="Clientes", review_status="reviewed")
        )
    path = tmp_path / "kinds.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        body = client.get(BASE + "/marketers?period=2026T1").json()
        assert body["total"] == 1
        assert {row["marketer_id"]: row["identity_status"] for row in body["items"]} == {
            "gas-test": "reviewed_identity",
        }
        assert client.get(BASE + "/series/gas-other").status_code == 404
        assert client.get(BASE + "/marketers?search=Other%20observed").json()["total"] == 0
        assert client.get(BASE + "/series/gas-test").json()["identity_status"] == "reviewed_identity"
        for kind in ("group", "direct-consumer", "unknown"):
            assert client.get(BASE + "/series/gas-new-" + kind).status_code == 404


def test_v2_canonical_company_combines_reviewed_reports_without_source_local_options(tmp_path):
    path = tmp_path / "canonical.sqlite"
    ingest(Evidence.model_validate(work_data()), path)
    with client_for(path) as client:
        for metric in ("clients", "sales"):
            companies = client.get(BASE + "/marketers", params={"metric": metric}).json()
            assert companies["total"] == 1
            assert companies["items"][0]["marketer_id"] == "gas-test"
            assert client.get(BASE + "/marketers", params={"metric": metric, "offset": 1}).json()["items"] == []
            body = client.get(BASE + "/series/gas-test", params={"metric": metric}).json()
            records = [record for point in body["items"] for record in point["records"]]
            assert [row["period"] for row in records] == ["2024T4", "2025T3", "2026T1"]
            assert [row["source"]["source_id"] for row in records] == ["earlier", "middle", "report"]
            assert all(row["review_status"] == "reviewed" for row in records)
            assert all(row["share"] == "0.1" for row in records)
            assert {row["observations"][0]["observed_name"] for row in records} == {
                "Earlier alias",
                "Middle alias",
                "Observed test",
            }
        old_name = client.get(BASE + "/marketers?search=Earlier%20alias&period=2026T1").json()
        assert old_name["total"] == 1 and old_name["items"][0]["observed_name"] == "Observed test"


def test_v1_database_without_extension_tables_keeps_legacy_contract(retail_database):
    with sqlite3.connect(retail_database) as connection:
        for table in ("source_audits", "observation_details", "unresolved_observations", "review_records"):
            connection.execute(f"DROP TABLE gas_retail_{table}")
    with client_for(retail_database) as client:
        value = series(client)
        assert value["source_audit"] is None and value["value"] == "30"
        assert value["observations"][0]["original_unit"] == "clients"
        assert client.get(BASE + "/marketers").json()["items"][0]["identity_status"] == "legacy_unspecified"


@pytest.fixture
def continuity_database(tmp_path):
    path = tmp_path / "continuity.sqlite"
    ingest(Evidence.model_validate(continuity_data()), path)
    return path


def test_company_pagination_and_total_deduplicate_before_offset(continuity_database):
    with client_for(continuity_database) as client:
        pages = [client.get(BASE + f"/marketers?limit=1&offset={offset}").json() for offset in range(3)]
        assert [page["total"] for page in pages] == [2, 2, 2]
        assert [page["items"][0]["marketer_id"] for page in pages[:2]] == ["gas-test", "gas-other"]
        assert pages[2]["items"] == []
        first = pages[0]["items"][0]
        assert first["company_name"] == "Canonical renamed supplier"
        assert first["observed_name"] == "Observed test" and first["source"]["source_id"] == "report"
        for metric in ("clients", "sales"):
            items = client.get(BASE + "/marketers?metric=" + metric).json()["items"]
            assert len({item["marketer_id"] for item in items}) == len(items)


@pytest.mark.parametrize("search", ["canonical RENAMED", "Earlier alias", "Middle alias", "Observed test"])
def test_company_search_matches_historical_alias_without_changing_representative(continuity_database, search):
    with client_for(continuity_database) as client:
        response = client.get(BASE + "/marketers", params={"search": search, "period": "2026T1"}).json()
        assert response["total"] == 1
        company = response["items"][0]
        assert company["marketer_id"] == "gas-test"
        assert company["observed_name"] == "Observed test"
        assert company["source"]["source_id"] == "report"
        assert client.get(BASE + "/marketers", params={"search": search, "offset": 1}).json()["items"] == []


def test_company_search_keeps_partial_aliases_private_and_scope_eligibility(continuity_database):
    with client_for(continuity_database) as client:
        assert client.get(BASE + "/marketers?search=Private%20alias").json()["total"] == 0
        assert client.get(BASE + "/marketers?search=Earlier%20alias&period=2025T4").json()["total"] == 0
        assert client.get(BASE + "/marketers?search=Earlier%20alias&scope=regulated").json()["total"] == 0
        response = client.get(BASE + "/marketers?search=Earlier%20alias&scope=liberalised").json()
        assert response["total"] == 1
        assert response["items"][0]["observed_name"] == "Middle alias"


def test_stable_company_series_spans_reports_preserves_names_and_hides_partial(continuity_database):
    with client_for(continuity_database) as client:
        for metric in ("clients", "sales"):
            body = client.get(BASE + f"/series/gas-test?metric={metric}&start_period=2024T4").json()
            assert body["company_name"] == "Canonical renamed supplier"
            records = [record for point in body["items"] for record in point["records"]]
            assert [row["period"] for row in records] == ["2024T4", "2025T3", "2026T1"]
            assert [row["source"]["source_id"] for row in records] == ["earlier", "middle", "report"]
            assert [row["observations"][0]["observed_name"] for row in records] == [
                "Earlier alias",
                "Middle alias",
                "Observed test",
            ]
            assert all(row["share"] == "0.1" and row["scope"] == "whole_market" for row in records)
            assert "Private alias" not in str(body) and "999" not in str(body)
            paged = client.get(
                BASE + f"/series/gas-test?metric={metric}&start_period=2025T3&end_period=2026T1&limit=1&offset=2"
            ).json()
            assert paged["total"] == 3 and paged["items"][0]["audit"]["period"] == "2026T1"
        liberalised = client.get(BASE + "/series/gas-test?scope=liberalised").json()
        records = [row for point in liberalised["items"] for row in point["records"]]
        assert len(records) == 1 and records[0]["period"] == "2025T3" and records[0]["share"] is None


def test_company_ids_and_alias_search_remain_revision_scoped(continuity_database):
    with client_for(continuity_database) as client:
        old = client.get(BASE + "/revisions").json()["items"][0]["load_id"]
    data = continuity_data()
    data["entities"][0]["name"] = "Revised canonical name"
    data["mappings"][0]["observed_name"] = "Revised current name"
    ingest(Evidence.model_validate(data), continuity_database)
    with client_for(continuity_database) as client:
        assert client.get(BASE + "/marketers?search=Revised").json()["total"] == 1
        assert client.get(BASE + f"/marketers?search=Revised&load_id={old}").json()["total"] == 0
        assert (
            client.get(BASE + f"/series/gas-test?load_id={old}").json()["company_name"] == "Canonical renamed supplier"
        )
        assert client.get(BASE + "/series/gas-test").json()["company_name"] == "Revised canonical name"


def test_equal_company_labels_do_not_merge_distinct_reviewed_identities(tmp_path):
    data = continuity_data()
    next(row for row in data["entities"] if row["gas_id"] == "gas-other")["name"] = data["entities"][0]["name"]
    path = tmp_path / "same-label.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        body = client.get(BASE + "/marketers?search=Canonical").json()
        assert body["total"] == 2
        assert {row["marketer_id"] for row in body["items"]} == {"gas-test", "gas-other"}


def test_stable_series_keeps_overlapping_reports_separate(tmp_path):
    data = continuity_data()
    data["sources"].append(dict(data["sources"][0], source_id="parallel"))
    for mapping in data["mappings"][:2]:
        data["mappings"].append(dict(mapping, source_id="parallel", mapping_id=mapping["mapping_id"] + "-parallel"))
    for row in list(data["observations"]):
        if row["month"].startswith("2026") and row["mapping_id"] in {"map-test", "map-total"}:
            data["observations"].append(
                dict(
                    row,
                    source_id="parallel",
                    mapping_id=row["mapping_id"] + "-parallel",
                    observation_id=row["observation_id"] + "-parallel",
                )
            )
    for audit in data["audits"]:
        if audit["period"] == "2026T1":
            audit["source_ids"].append("parallel")
    path = tmp_path / "parallel.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        assert client.get(BASE + "/marketers").json()["total"] == 2
        body = client.get(BASE + "/series/gas-test?start_period=2026T1").json()
        records = body["items"][0]["records"]
        assert len(records) == 2
        assert {row["source"]["source_id"] for row in records} == {"report", "parallel"}
        assert all(row["value"] == "30" and row["share"] == "0.1" for row in records)
        assert all(row["denominator"]["source"]["source_id"] == row["source"]["source_id"] for row in records)


def client_for(path):
    return TestClient(create_app(Settings(database=path, development_mode=True)))


def series(client, suffix=""):
    response = client.get(BASE + "/series/gas-test?start_period=2026T1" + suffix)
    assert response.status_code == 200, response.text
    return response.json()["items"][0]["records"][0]


def test_reviewed_values_names_units_denominator_and_provenance(retail_database):
    with client_for(retail_database) as client:
        clients = series(client)
        assert clients["value"] == "30" and clients["share"] == "0.1"
        assert clients["denominator"]["gas_id"] == "gas-total"
        assert clients["denominator"]["value"] == "300"
        assert clients["source"]["published_on"] is None
        assert clients["source"]["sha256"] == "a" * 64
        assert clients["source"]["reuse_status"] == "review_pending"
        assert clients["observations"][-1]["observed_name"] == "Observed test"
        assert clients["observations"][-1]["page"] == 2
        assert clients["observations"][-1]["raw_value"] == "30"
        sales = series(client, "&metric=sales")
        assert sales["value"] == "60000" and sales["unit"] == "MWh"
        assert sales["original_value"] == "60" and sales["original_unit"] == "GWh"
        assert len(sales["observations"]) == 3 and sales["share"] == "0.1"


def test_coverage_and_partial_values_are_not_published(retail_database):
    with client_for(retail_database) as client:
        response = client.get(BASE + "/periods?offset=88").json()
        assert response["total"] == 90 and response["complete"] is False
        assert [item["audit"]["status"] for item in response["items"]] == ["partial", "reviewed"]
        assert [item["reviewed_retailer_count"] for item in response["items"]] == [0, 1]
        result = client.get(BASE + "/series/gas-test?start_period=2025T3").json()
        assert [point["availability"] for point in result["items"]] == ["unreviewed", "unreviewed", "reviewed"]
        assert result["items"][1]["records"] == [] and "999" not in str(result)
        assert result["geographic_scope"] == "source_defined"
        assert client.get(BASE + "/marketers?period=2025T4").json()["items"] == []


def test_observed_retailer_lists_filter_groups_totals_and_search(retail_database):
    with client_for(retail_database) as client:
        result = client.get(BASE + "/marketers").json()
        assert result["total"] == 1 and result["limit"] == 50
        assert result["items"][0]["observed_name"] == "Observed test"
        assert client.get(BASE + "/marketers?search=TEST").json()["total"] == 1
        assert client.get(BASE + "/marketers?search=%").json()["total"] == 0
        assert client.get(BASE + "/marketers?scope=liberalised").json()["total"] == 0
        assert client.get(BASE + "/marketers?limit=1&offset=1").json()["items"] == []
        for name in ("group", "rest", "total", "unknown", "cur-0"):
            assert client.get(BASE + f"/series/gas-{name}").status_code == 404


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=101",
        "offset=-1",
        "offset=10001",
        "load_id=bad",
        "province_code=28",
        "community_code=13",
        "municipality_code=28079",
        "sector=gas",
    ],
)
def test_lists_reject_invalid_and_geographic_filters(retail_database, query):
    with client_for(retail_database) as client:
        for endpoint in (BASE + "/periods", BASE + "/marketers", BASE + "/revisions", "/v1/gas/reference-marketers"):
            assert client.get(endpoint + "?" + query).status_code == 422


@pytest.mark.parametrize(
    "query",
    [
        "limit=121",
        "offset=10001",
        "metric=purchases",
        "scope=national",
        "start_period=2026T2&end_period=2026T1",
        "end_period=bad",
        "province_code=28",
    ],
)
def test_series_validation(retail_database, query):
    with client_for(retail_database) as client:
        assert client.get(BASE + "/series/gas-test?" + query).status_code == 422
        assert client.get(BASE + "/series/R2-001").status_code == 422


@pytest.mark.parametrize("status", ["zero", "missing", "suppressed", "source_error", "bounded"])
def test_numeric_states_remain_distinct(tmp_path, status):
    data = evidence_data()
    data["observations"][2].update(
        status=status, value="0" if status == "zero" else None, upper_bound="50" if status == "bounded" else None
    )
    path = tmp_path / "states.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        row = series(client)
        assert row["status"] == status
        assert row["value"] == ("0" if status == "zero" else None)
        assert row["share"] == ("0" if status == "zero" else None)
        assert row["upper_bound"] == ("50" if status == "bounded" else None)
        assert row["upper_bound_exclusive"] is True


@pytest.mark.parametrize(
    "change,expected",
    [
        ("zero", "zero"),
        ("scope", "missing"),
        ("source", "missing"),
        ("duplicate", "ambiguous"),
        ("bounded", "unavailable"),
    ],
)
def test_denominator_identity_and_unavailability(tmp_path, change, expected):
    data = evidence_data()
    total_rows = [row for row in data["observations"] if row["mapping_id"] == "map-total"]
    if change == "duplicate":
        data["entities"].append(dict(data["entities"][1], gas_id="gas-total-other"))
        data["mappings"].append(
            dict(data["mappings"][1], gas_id="gas-total-other", mapping_id="map-other", observed_name="Other total")
        )
        data["observations"].extend(
            dict(row, observation_id=row["observation_id"] + "-other", mapping_id="map-other") for row in total_rows
        )
    elif change == "source":
        data["mappings"][1]["source_id"] = "guide"
        for audit in data["audits"]:
            if audit["period"] == "2026T1":
                audit["source_ids"].append("guide")
        for row in total_rows:
            row["source_id"] = "guide"
    else:
        for row in total_rows:
            if change == "scope":
                row["scope"] = "liberalised"
            elif change == "zero":
                row.update(status="zero", value="0")
            else:
                row.update(status="bounded", value=None, upper_bound="500")
    path = tmp_path / "denominator.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        row = series(client)
        assert row["denominator_status"] == expected and row["share"] is None


def test_missing_sales_month_duplicates_and_kwh_conversion(tmp_path):
    data = evidence_data()
    data["observations"] = [row for row in data["observations"] if row["observation_id"] != "test-sales-1"]
    data["observations"].append(dict(data["observations"][2], observation_id="repeat"))
    path = tmp_path / "missing.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        assert series(client)["status"] == "source_error"
        sales = series(client, "&metric=sales")
        assert sales["status"] == "missing" and sales["missing_months"] == ["2026-01"]
    data = evidence_data()
    for row in data["observations"]:
        if row["metric"] == "sales":
            row["unit"] = "kWh"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        assert series(client, "&metric=sales")["value"] == "0.060"


def test_revisions_are_immutable_selected_and_catalogue_independent(retail_database):
    with client_for(retail_database) as client:
        old = client.get(BASE + "/revisions").json()["items"][0]["load_id"]
    data = evidence_data()
    data["observations"][2]["value"] = "31"
    new = ingest(Evidence.model_validate(data), retail_database)
    with client_for(retail_database) as client:
        assert series(client)["value"] == "31"
        assert series(client, "&load_id=" + old)["value"] == "30"
        assert client.get(BASE + "/revisions").json()["total"] == 2
        assert client.get(BASE + "/revisions?load_id=" + old).json()["total"] == 1
        assert client.get(BASE + "/periods?load_id=" + "f" * 64).status_code == 404
        catalogue = client.get("/v1/gas/reference-marketers").json()
        assert catalogue["revision"]["load_id"] == new and catalogue["total"] == 4
        assert all(len(row["observations"]) == 2 for row in catalogue["items"])
        assert catalogue["items"][0]["observations"][0]["evidence_on"] == "2022-11-14"
        assert catalogue["items"][0]["observations"][1]["source"]["published_on"] is None
        assert "price" not in str(catalogue)


def test_revision_coverage_is_bounded_and_links_full_audits(retail_database):
    with client_for(retail_database) as client:
        revision = client.get(BASE + "/revisions").json()["items"][0]
        assert revision["issue_count"] == 178
        assert revision["issues_truncated"] is True and len(revision["issues"]) == 10
        assert len(revision["coverage"]) == 2
        for coverage in revision["coverage"]:
            assert {item["status"]: item["periods"] for item in coverage["counts"]} == {
                "not_reviewed": 88,
                "partial": 1,
                "reviewed": 1,
            }
            audits = client.get(coverage["audits_url"]).json()
            assert audits["total"] == 90 and audits["revision"]["load_id"] == revision["load_id"]
        issue = revision["issues"][0]
        audit = client.get(issue["audit_url"]).json()["items"][0]["audit"]
        assert audit["period"] == issue["period"] and audit["note"] == issue["note"]


def test_reviewed_only_ids_and_explicit_unavailable_audits(tmp_path):
    data = evidence_data()
    data["entities"].append(dict(data["entities"][0], gas_id="gas-partial"))
    data["mappings"].append(
        dict(data["mappings"][0], gas_id="gas-partial", mapping_id="map-partial", observed_name="Partial only")
    )
    data["observations"].append(
        dict(data["observations"][-1], observation_id="private-partial", mapping_id="map-partial")
    )
    for audit in data["audits"]:
        if audit["period"] == "2025T3":
            audit.update(status="source_error", source_ids=["report"], note="Known synthetic source defect.")
    path = tmp_path / "partial.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        assert client.get(BASE + "/series/gas-partial").status_code == 404
        assert "Partial only" not in client.get(BASE + "/marketers").text
        points = client.get(BASE + "/series/gas-test?start_period=2025T3").json()["items"]
        assert points[0]["availability"] == "unavailable"
        assert points[0]["audit"]["status"] == "source_error" and points[0]["records"] == []


def test_bounded_sales_converts_exclusive_upper_bound(tmp_path):
    data = evidence_data()
    for row in data["observations"]:
        if row["observation_id"] == "test-sales-3":
            row.update(status="bounded", value=None, upper_bound="50")
    path = tmp_path / "bounded-sales.sqlite"
    ingest(Evidence.model_validate(data), path)
    with client_for(path) as client:
        row = series(client, "&metric=sales")
        assert row["status"] == "bounded" and row["value"] is None and row["share"] is None
        assert row["original_upper_bound"] == "80" and row["upper_bound"] == "80000"
        assert row["input_statuses"] == ["exact", "exact", "bounded"]


def test_cache_hit_avoids_database_keeps_rate_limits_and_separates_queries(retail_database):
    class MemoryRedis:
        def __init__(self):
            self.values = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ex):
            self.values[key] = value

        def close(self):
            pass

    app = create_app(Settings(database=retail_database, development_mode=True))
    app.state.response_cache = RedisResponseCache(MemoryRedis(), "gas-retail-test", 300)
    paths = [
        BASE + "/periods",
        BASE + "/marketers",
        BASE + "/series/gas-test",
        BASE + "/revisions",
        "/v1/gas/reference-marketers",
    ]
    with TestClient(app) as client:
        for path in paths:
            assert client.get(path).headers["X-Cache"] == "MISS"
        assert client.get(paths[2] + "?metric=sales").headers["X-Cache"] == "MISS"
        assert client.get(paths[2] + "?scope=liberalised").headers["X-Cache"] == "MISS"
        for _ in range(2):
            assert client.get(BASE + "/series/gas-unknown").status_code == 404
        assert len(app.state.response_cache.client.values) == 7

        @event.listens_for(app.state.database_engine, "checkout")
        def forbid_database(*args):
            raise AssertionError("Cache hit opened a database connection")

        for path in paths:
            assert client.get(path).headers["X-Cache"] == "HIT"
        app.state.settings = replace(app.state.settings, development_mode=False, request_limit=1)
        assert client.get(paths[0]).headers["X-Cache"] == "HIT"
        assert client.get(paths[0]).status_code == 429


def test_no_startup_ddl_and_missing_schema_is_unavailable(tmp_path):
    path = tmp_path / "empty.sqlite"
    with sqlite3.connect(path):
        pass
    with client_for(path) as client:
        assert client.get(BASE + "/periods").status_code == 503
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []


@pytest.mark.parametrize("evidence_version", [1, 2])
def test_postgres_gas_retail_parity_and_read_only(continuity_database, evidence_version):
    retail_database = continuity_database
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set TEST_POSTGRES_URL to an isolated PostgreSQL service")
    parsed = make_url(url)
    if parsed.host not in {"localhost", "127.0.0.1", "::1", "postgres"}:
        pytest.skip("Gas retail parity requires a local isolated service")
    if evidence_version == 2:
        data = work_data()
        add_partial_alternative(data)
        ingest(Evidence.model_validate(data), retail_database)
    with sqlite3.connect(retail_database) as source:
        statements = [
            statement for statement in _ordered_dump(source) if statement not in {"BEGIN TRANSACTION;", "COMMIT;"}
        ]
    schema = "test_gas_api_" + uuid4().hex
    admin = create_engine(parsed.set(drivername="postgresql+psycopg"))
    remote = create_app(Settings(database_url=url, development_mode=True))
    try:
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            for statement in statements:
                connection.exec_driver_sql(statement)

        @event.listens_for(remote.state.database_engine, "begin")
        def select_schema(connection):
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')

        with TestClient(remote) as postgres, client_for(retail_database) as sqlite:
            for path in (
                BASE + "/periods",
                BASE + "/marketers",
                BASE + "/marketers?search=test",
                BASE + "/marketers?search=Earlier%20alias&period=2026T1",
                BASE + "/marketers?search=canonical&limit=1&offset=1",
                BASE + "/marketers?limit=1&offset=1",
                BASE + "/series/gas-test",
                BASE + "/series/gas-test?metric=sales",
                BASE + "/revisions",
                "/v1/gas/reference-marketers",
            ):
                actual, expected = postgres.get(path), sqlite.get(path)
                assert actual.status_code == expected.status_code == 200
                assert actual.json() == expected.json()
            with remote.state.database_engine.connect() as connection:
                assert connection.scalar(text("SHOW transaction_read_only")) == "on"
                with pytest.raises(DBAPIError) as error:
                    connection.exec_driver_sql("DELETE FROM gas_retail_observations")
                assert error.value.orig.sqlstate == "25006"
    finally:
        remote.state.database_engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        admin.dispose()

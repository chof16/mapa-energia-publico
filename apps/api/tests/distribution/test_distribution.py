"""The snapshot makes positive, provincial claims without implying completeness."""

import sqlite3
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from electricity_map_api.config import Settings
from electricity_map_api.distribution.store import build_database, load_manifest
from electricity_map_api.main import create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError

_database_directory = TemporaryDirectory()


@lru_cache(maxsize=1)
def distribution_database() -> Path:
    path = Path(_database_directory.name) / "distribution.sqlite"
    build_database(path)
    return path


def client() -> TestClient:
    return TestClient(create_app(Settings(database=distribution_database(), development_mode=True)))


def test_partial_provincial_presence_preserves_claims_and_provenance() -> None:
    response = client().get("/v1/distribution/provinces/24")
    assert response.status_code == 200
    body = response.json()
    assert body["sector"] == "electricity"
    assert body["province_code"] == "24"
    assert body["snapshot_date"] == "2026-10-07"
    assert body["scope"] == "provincial_presence"
    assert body["complete"] is False
    assert {item["distributor_code"] for item in body["items"]} == {"R1-299", "R1-001", "R1-002"}
    for item in body["items"]:
        assert item["registry_source_url"].startswith("https://www.boe.es/")
        assert item["cor"] is None
        assert item["corporate_group"] is not None
        assert item["evidence"]["source_url"].startswith("https://www.endesa.com/")
        assert item["evidence"]["published_on"] == "2022-03-01"
        assert item["evidence"]["checked_on"] == "2026-10-03"
        assert "León" in item["evidence"]["geographic_claim"]
    assert (
        "oeste"
        in next(item for item in body["items"] if item["distributor_code"] == "R1-002")["evidence"]["geographic_claim"]
    )


def test_summary_counts_only_documented_presences_and_keeps_unknown_provinces_out() -> None:
    api = client()
    response = api.get("/v1/distribution/provinces")
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "documented_provincial_presence"
    assert body["snapshot_date"] == "2026-10-07"
    assert body["complete"] is False
    by_code = {item["province_code"]: item["documented_distributor_count"] for item in body["items"]}
    assert by_code["24"] == 3
    assert by_code["28"] == 2
    assert by_code["46"] == 1
    assert {"03", "08", "17", "21", "34", "41", "43"} <= by_code.keys()
    assert all(by_code[code] == 1 for code in ("08", "21", "41"))
    assert len(by_code) == 48
    assert {"09", "12", "35", "47"}.isdisjoint(by_code)
    assert len(by_code) == len(body["items"])
    for code, count in by_code.items():
        assert count == len(api.get(f"/v1/distribution/provinces/{code}").json()["items"])
    assert api.get("/v1/distribution/provinces?sector=gas").json()["items"] == []
    assert api.get("/v1/distribution/provinces?sector=coal").status_code == 422


def test_absent_claim_is_unknown_and_gas_is_pending() -> None:
    api = client()
    for province in ("09", "12", "35", "47"):
        unknown = api.get(f"/v1/distribution/provinces/{province}").json()
        assert unknown["items"] == []
        assert unknown["complete"] is False
    gas = api.get("/v1/distribution/provinces/24?sector=gas").json()
    assert gas["sector"] == "gas"
    assert gas["items"] == []
    assert gas["complete"] is False


def test_asturias_has_distinct_official_evidence_for_hidrocantabrico() -> None:
    items = client().get("/v1/distribution/provinces/33").json()["items"]
    by_code = {item["distributor_code"]: item for item in items}
    assert set(by_code) == {"R1-008", "R1-005"}
    official = by_code["R1-008"]["evidence"]
    assert official["source_url"] == "https://www.boe.es/diario_boe/txt.php?id=BOE-B-2026-2338"
    assert official["published_on"] == "2026-01-29"
    assert official["confidence"] == "official_document"
    assert "Ribadesella" in official["geographic_claim"]
    assert by_code["R1-005"]["evidence"]["confidence"] == "other_operator_reported"


@pytest.mark.parametrize(
    ("province", "distributor", "source_url", "published_on", "place"),
    [
        (
            "46",
            "R1-001",
            "https://www.iberdrola.com/sala-comunicacion/noticias/detalle/iberdrola-invierte-100-millones-de-euros-en-el-rediseno-de-la-red-electrica-afectada-por-la-dana",
            "2025-01-16",
            "l'Horta Sud",
        ),
        (
            "15",
            "R1-002",
            "https://www.xunta.gal/dog/Publicados/2024/20240318/AnuncioG0692-260224-0003_es.html",
            "2024-03-18",
            "Aldea Merexo",
        ),
        (
            "27",
            "R1-002",
            "https://www.xunta.gal/dog/Publicados/2025/20250528/AnuncioG0763-080525-0009_es.html",
            "2025-05-28",
            "Quiroga",
        ),
        (
            "32",
            "R1-002",
            "https://www.xunta.gal/dog/Publicados/2025/20250528/AnuncioG0763-080525-0009_es.html",
            "2025-05-28",
            "A Rúa",
        ),
        (
            "36",
            "R1-002",
            "https://www.xunta.gal/dog/Publicados/2023/20230508/AnuncioV0653-170423-0008_es.html",
            "2023-05-08",
            "Mourente",
        ),
    ],
)
def test_new_claims_keep_individual_source_provenance(
    province: str, distributor: str, source_url: str, published_on: str, place: str
) -> None:
    response = client().get(f"/v1/distribution/provinces/{province}")
    assert response.status_code == 200
    body = response.json()
    assert body["complete"] is False
    matching = [item for item in body["items"] if item["distributor_code"] == distributor]
    assert len(matching) == 1
    item = matching[0]
    assert item["registry_source_url"].endswith("BOE-A-2026-12790.pdf")
    assert item["cor"] is None
    assert item["evidence"]["source_url"] == source_url
    assert item["evidence"]["published_on"] == published_on
    assert item["evidence"]["checked_on"] == "2026-10-04"
    assert item["evidence"]["confidence"] == (
        "group_first_party_reported" if distributor == "R1-001" else "official_document"
    )
    assert place in item["evidence"]["geographic_claim"]


@pytest.mark.parametrize(
    ("province", "distributor", "source_id", "published_on", "place"),
    [
        ("08", "R1-299", "BOE-B-2022-15582", "2022-05-18", "Vilanova i la Geltrú"),
        ("21", "R1-299", "BOE-B-2023-926", "2023-01-12", "Almonte"),
        ("41", "R1-299", "BOE-B-2024-39884", "2024-11-04", "Agribética-Cantillana"),
        ("17", "R1-299", "BOE-B-2026-11760", "2026-04-16", "Empordanet-Bellcaire"),
        ("43", "R1-299", "BOE-B-2026-21758", "2026-06-26", "TEIXETA2"),
        ("03", "R1-001", "2024_14076_es.pdf", "2025-01-14", "Xixona-Rabasa"),
        ("34", "R1-005", "BOCYL-D-07012026-3-4.pdf", "2026-01-07", "Reparto Helechar"),
    ],
)
def test_official_asset_claims_have_separate_dates_and_limited_geography(
    province: str, distributor: str, source_id: str, published_on: str, place: str
) -> None:
    body = client().get(f"/v1/distribution/provinces/{province}").json()
    assert body["snapshot_date"] == "2026-10-07"
    assert body["complete"] is False
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["distributor_code"] == distributor
    assert item["registry_source_url"].endswith("BOE-A-2026-12790.pdf")
    assert item["cor"] is None
    assert item["corporate_group"]["evidence"]["checked_on"] == "2026-10-04"
    evidence = item["evidence"]
    assert evidence["source_url"].endswith(source_id)
    assert evidence["published_on"] == published_on
    assert evidence["checked_on"] == "2026-10-05"
    assert evidence["confidence"] == "official_document"
    assert place in evidence["geographic_claim"]


@pytest.mark.parametrize(
    ("province", "distributor", "group", "source_url", "published_on"),
    [
        ("06", "R1-299", "Endesa", "https://www.endesa.com/es/sobre-endesa/quienes-somos/sociedades", None),
        ("46", "R1-001", "Iberdrola", "https://www.iberdrola.com/gobierno-corporativo/estructura", None),
        ("15", "R1-002", "Naturgy", "https://www.cnmc.es/prensa/archivo-ufd-20260519", "2026-05-19"),
        (
            "33",
            "R1-008",
            "EDP",
            "https://www.edp.com/sites/default/files/document/2025-09/Pol%C3%ADtica%20de%20Compliance%20Penal%20EDPR%20%26%20EDP%20Espa%C3%B1a_julio%202025.pdf",
            "2025-07-25",
        ),
        (
            "39",
            "R1-005",
            "EDP",
            "https://www.edp.com/sites/default/files/document/2025-09/Pol%C3%ADtica%20de%20Compliance%20Penal%20EDPR%20%26%20EDP%20Espa%C3%B1a_julio%202025.pdf",
            "2025-07-25",
        ),
    ],
)
def test_corporate_group_is_sourced_separately_from_coverage_and_cor(
    province: str, distributor: str, group: str, source_url: str, published_on: str | None
) -> None:
    items = client().get(f"/v1/distribution/provinces/{province}").json()["items"]
    item = next(item for item in items if item["distributor_code"] == distributor)
    association = item["corporate_group"]
    assert association["group_name"] == group
    assert association["evidence"]["source_url"] == source_url
    assert association["evidence"]["published_on"] == published_on
    assert association["evidence"]["checked_on"] == "2026-10-04"
    assert item["cor"] is None
    assert item["evidence"]["source_url"] != source_url


def test_new_evidence_does_not_replace_older_claim_in_the_same_province() -> None:
    items = client().get("/v1/distribution/provinces/15").json()["items"]
    assert {item["distributor_code"] for item in items} == {"R1-299", "R1-002"}
    assert (
        next(item for item in items if item["distributor_code"] == "R1-299")["evidence"]["checked_on"] == "2026-10-03"
    )


@pytest.mark.parametrize(
    ("province", "distributor", "source_id", "place"),
    [
        ("04", "R1-299", "BOE-B-2021-44618", "Purchena"),
        ("07", "R1-299", "BOE-B-2024-22592", "Es Mercadal"),
        ("11", "R1-299", "BOE-B-2026-25688", "Puerto Real"),
        ("14", "R1-299", "BOE-B-2026-7401", "Peñaflo_1"),
        ("18", "R1-299", "BOE-B-2026-13418", "Montefrío"),
        ("22", "R1-299", "BOE-A-2023-25262", "Huesca"),
        ("23", "R1-299", "BOE-B-2026-21546", "Rus"),
        ("25", "R1-299", "BOE-B-2022-18219", "Rialp"),
        ("29", "R1-299", "BOE-A-2025-5332", "Buenavista"),
        ("38", "R1-299", "BOE-B-2025-27901", "Arico"),
        ("44", "R1-299", "BOE-B-2026-14564", "Andorra"),
        ("50", "R1-299", "BOE-B-2025-23023", "Pitarco"),
        ("01", "R1-001", "BOE-B-2026-27432", "Puentelarrá"),
        ("05", "R1-001", "BOCYL-D-24042024-7.pdf", "Arenas de San Pedro"),
        ("20", "R1-001", "BOE-B-2023-4385", "Urumea"),
        ("26", "R1-001", "BOE-B-2023-20550", "Alcanadre"),
        ("31", "R1-001", "BOE-B-2023-20550", "Mendavia"),
        ("37", "R1-001", "BOCYL-D-16102024-6.pdf", "Salamanca"),
        ("48", "R1-001", "BOE-B-2021-33841", "Abanto"),
        ("49", "R1-001", "BOCYL-D-14042023-13.pdf", "Fariza"),
        ("51", "R1-030", "BOE-B-2021-51380", "puerto de Ceuta"),
        ("52", "R1-027", "/articulo/397", "General Villalba"),
    ],
)
def test_reviewed_claim_is_in_both_incomplete_endpoints(
    province: str, distributor: str, source_id: str, place: str
) -> None:
    api = client()
    detail = api.get(f"/v1/distribution/provinces/{province}")
    summary = api.get("/v1/distribution/provinces")
    assert detail.status_code == summary.status_code == 200
    assert detail.json()["complete"] is summary.json()["complete"] is False
    assert detail.json()["snapshot_date"] == summary.json()["snapshot_date"] == "2026-10-07"
    assert len(detail.json()["items"]) == 1
    item = detail.json()["items"][0]
    assert item["distributor_code"] == distributor
    assert item["evidence"]["source_url"].endswith(source_id)
    assert item["evidence"]["source_title"]
    assert item["evidence"]["published_on"] is not None
    assert item["evidence"]["checked_on"] == "2026-10-07"
    assert item["evidence"]["confidence"] == "official_document"
    assert place in item["evidence"]["geographic_claim"]
    assert item["cor"] is None
    if province in {"51", "52"}:
        assert item["corporate_group"] is None
        assert item["registry_source_url"].endswith("BOE-A-2025-4506")
    else:
        assert item["corporate_group"] is not None
        assert item["registry_source_url"].endswith("BOE-A-2026-12790.pdf")
    by_code = {row["province_code"]: row for row in summary.json()["items"]}
    assert by_code[province]["documented_distributor_count"] == 1


def test_invalid_province_and_unknown_parameters_are_rejected() -> None:
    api = client()
    for path in (
        "/v1/distribution/provinces/00",
        "/v1/distribution/provinces/53",
        "/v1/distribution/provinces/7",
        "/v1/distribution/provinces/24?sector=coal",
        "/v1/distribution/provinces/24?period=2024T4",
    ):
        assert api.get(path).status_code == 422


def test_review_status_controls_published_claims_and_summary(tmp_path: Path) -> None:
    database = tmp_path / "distribution.sqlite"
    build_database(database)
    app = create_app(Settings(database=database, development_mode=True))
    api = TestClient(app)
    assert len(api.get("/v1/distribution/provinces/51").json()["items"]) == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM claim_decision WHERE status = 'rejected'").fetchone()[0] == 4
        connection.execute(
            "UPDATE claim_decision SET status = 'superseded', decision_reason = ? WHERE province_code = '51'",
            ("Evidence superseded by a later review",),
        )
    assert api.get("/v1/distribution/provinces/51").json()["items"] == []
    assert "51" not in {item["province_code"] for item in api.get("/v1/distribution/provinces").json()["items"]}
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT decision_reason FROM claim_decision WHERE province_code = '51'").fetchone()[0]
            == "Evidence superseded by a later review"
        )


def test_invalid_review_cannot_replace_existing_database(tmp_path: Path) -> None:
    database = tmp_path / "distribution.sqlite"
    build_database(database)
    original = database.read_bytes()
    invalid = deepcopy(load_manifest())
    invalid["claims"][0]["status"] = "accepted"
    invalid["claims"][0]["evidence"] = None
    with pytest.raises(ValidationError):
        build_database(database, invalid)
    assert database.read_bytes() == original


def test_unconfigured_distribution_database_is_unavailable() -> None:
    api = TestClient(create_app(Settings(request_limit=120)))
    response = api.get("/v1/distribution/provinces")
    assert response.status_code == 503
    assert response.json()["detail"] == "Distribution database is unavailable"


def test_rebuilding_distribution_updates_only_coverage_tables(tmp_path: Path) -> None:
    database = tmp_path / "combined.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE market_marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO market_marker VALUES ('preserved')")
    inode = database.stat().st_ino
    build_database(database)
    build_database(database)
    assert database.stat().st_ino == inode
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM market_marker").fetchone() == ("preserved",)
        assert connection.execute("SELECT COUNT(*) FROM claim_decision").fetchone() == (63,)

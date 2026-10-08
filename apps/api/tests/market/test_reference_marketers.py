"""COR status is published separately from distributor presence."""

from pathlib import Path

from electricity_map_api.config import Settings
from electricity_map_api.distribution.store import build_database
from electricity_map_api.main import create_app
from fastapi.testclient import TestClient


def client(distribution_database: Path | None = None) -> TestClient:
    settings = Settings(database=distribution_database, development_mode=True)
    return TestClient(create_app(settings))


def test_reference_marketers_have_evidence_and_do_not_assign_distributors(tmp_path: Path) -> None:
    database = tmp_path / "distribution.sqlite"
    build_database(database)
    api = client(database)
    response = api.get("/v1/market/reference-marketers")
    assert response.status_code == 200
    body = response.json()
    assert body["sector"] == "electricity"
    assert body["snapshot_date"] == "2026-10-04"
    assert body["scope"] == "reference_marketers"
    assert body["designation_source_url"].startswith("https://www.cnmc.es/")
    assert body["code_source_url"].startswith("https://data.cnmc.es/")
    assert body["code_source_period"] == "2025T4"
    assert body["code_source_metadata_modified"] == "2026-09-16T09:54:27.287603"
    assert body["attribution"].startswith("Origen de los datos: Comisión Nacional")
    by_code = {item["marketer_code"]: item for item in body["items"]}
    assert set(by_code) == {"R2-292", "R2-329", "R2-356", "R2-284", "R2-290", "R2-540", "R2-532", "R2-530"}
    assert by_code["R2-532"]["territorial_limit"] == "melilla"
    assert by_code["R2-530"]["territorial_limit"] == "ceuta"
    assert all(item["territorial_limit"] is None for code, item in by_code.items() if code not in {"R2-532", "R2-530"})
    assert all("distributor_code" not in item for item in body["items"])
    province = api.get("/v1/distribution/provinces/24").json()
    assert all(item["cor"] is None for item in province["items"])


def test_reference_marketers_reject_unknown_parameters_and_leave_gas_pending() -> None:
    api = client()
    assert api.get("/v1/market/reference-marketers?period=2025T4").status_code == 422
    assert api.get("/v1/market/reference-marketers?sector=coal").status_code == 422
    gas = api.get("/v1/market/reference-marketers?sector=gas").json()
    assert gas["sector"] == "gas"
    assert gas["items"] == []
    assert gas["designation_source_url"] is None
    assert gas["code_source_url"] is None

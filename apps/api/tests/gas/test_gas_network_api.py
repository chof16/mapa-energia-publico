"""Gas network presence semantics and cache isolation with synthetic source observations."""

import sqlite3
from dataclasses import replace

import pytest
from electricity_map_api.cache import RedisResponseCache
from electricity_map_api.config import Settings
from electricity_map_api.main import create_app
from electricity_map_ingestion import gas_distribution_store as store
from electricity_map_ingestion.gas_distribution import NetworkRow
from fastapi.testclient import TestClient
from sqlalchemy import event


@pytest.fixture
def network_database(tmp_path):
    path = tmp_path / "network.sqlite"
    with sqlite3.connect(path) as connection:
        store.initialize(connection)
        store.write_load(connection, [NetworkRow(4, "01", "Municipio", "Anterior SA", 1)], "a" * 64)
        store.write_load(
            connection,
            [
                NetworkRow(4, "01", "Municipio", "Uno SA", 10),
                NetworkRow(5, "01", "Municipio", "Uno SA", 10),
                NetworkRow(6, "01", "Municipio", "Dos SA", 0),
                NetworkRow(7, "28", "Otro municipio", "Uno SA", 30),
            ],
            "b" * 64,
        )
    return path


def test_network_history_pagination_and_unknown(network_database):
    with TestClient(create_app(Settings(database=network_database, development_mode=True))) as client:
        path = "/v1/gas/distribution"
        summary = client.get(path + "/provinces?limit=1").json()
        assert summary["total"] == 2 and summary["complete"] is False
        assert summary["source"]["period"] == "2019-06"
        assert summary["source"]["reuse_status"] == "review_pending"
        assert "license_id" not in summary["source"]
        assert summary["items"] == [
            {"province_code": "01", "documented_distributor_count": 2, "source_row_count": 3, "supply_points": 20}
        ]
        assert client.get(path + "/provinces?limit=1&offset=1").json()["items"][0]["province_code"] == "28"
        detail = client.get(path + "/provinces/01").json()
        assert detail["items"] == [
            {"distributor_name": "Dos SA", "source_row_count": 1, "supply_points": 0},
            {"distributor_name": "Uno SA", "source_row_count": 2, "supply_points": 20},
        ]
        unknown = client.get(path + "/provinces/35").json()
        assert unknown["items"] == [] and unknown["complete"] is False
        history = client.get(path + "/provinces/01?load_id=" + "a" * 64).json()
        assert history["items"][0]["distributor_name"] == "Anterior SA"
        assert client.get(path + "/revisions?limit=1").json()["total"] == 2
        assert client.get(path + "/provinces?load_id=" + "c" * 64).status_code == 404
        for suffix in (
            "/provinces/1",
            "/provinces/53",
            "/provinces?limit=101",
            "/provinces?offset=10001",
            "/provinces?period=2026",
            "/provinces?load_id=invalid",
        ):
            assert client.get(path + suffix).status_code == 422


def test_no_startup_migration(tmp_path):
    database = tmp_path / "empty.sqlite"
    sqlite3.connect(database).close()
    with TestClient(create_app(Settings(database=database, development_mode=True))) as client:
        assert client.get("/v1/gas/distribution/provinces").status_code == 503
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []


def test_gas_exposes_only_distributor_map_contracts(network_database):
    app = create_app(Settings(database=network_database, development_mode=True))
    with TestClient(app) as client:
        for endpoint in (
            "datasets",
            "observations",
            "companies",
            "shares",
            "periods",
            "series",
            "snapshots",
            "revisions",
            "regulated-suppliers",
        ):
            assert client.get(f"/v1/gas/{endpoint}").status_code == 404
        metadata = client.get("/v1").json()
        assert metadata["gas_distribution_api"] == "/v1/gas/distribution"
        assert "gas_api" not in metadata
    from electricity_map_api.models import Base

    assert {name for name in Base.metadata.tables if name.startswith("gas_network_")} == {
        "gas_network_loads",
        "gas_network_rows",
    }


def test_cached_detail_isolated_by_province_and_revision(network_database):
    class MemoryRedis:
        def __init__(self):
            self.values = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ex):
            self.values[key] = value

        def close(self):
            pass

    app = create_app(Settings(database=network_database, development_mode=True))
    app.state.response_cache = RedisResponseCache(MemoryRedis(), "gas-network-test", 300)
    with TestClient(app) as client:
        path = "/v1/gas/distribution/provinces/"
        first = client.get(path + "01")
        assert first.headers["X-Cache"] == "MISS"
        assert client.get(path + "28").json()["items"][0]["supply_points"] == 30
        assert client.get(path + "01?load_id=" + "a" * 64).json()["items"][0]["distributor_name"] == "Anterior SA"

        @event.listens_for(app.state.database_engine, "checkout")
        def forbid_database(*args):
            raise AssertionError("Cache hit opened database")

        hit = client.get(path + "01")
        assert hit.headers["X-Cache"] == "HIT" and hit.json() == first.json()
        app.state.settings = replace(app.state.settings, development_mode=False, request_limit=1)
        assert client.get(path + "01").headers["X-Cache"] == "HIT"
        assert client.get(path + "01").status_code == 429

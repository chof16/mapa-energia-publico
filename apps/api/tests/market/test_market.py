"""Market API contracts against a small imported database."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from electricity_map_api.config import Settings
from electricity_map_api.database import create_database_engine, get_session
from electricity_map_api.main import create_app
from electricity_map_api.market.models import MarketLoad, MarketRow
from electricity_map_ingestion.cnmc_market import ATTRIBUTION, CONDITIONS_URL
from electricity_map_ingestion.market_store import initialize, write_quarter
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import OperationalError
from starlette.requests import Request


def _client(path: Path | None) -> TestClient:
    settings = Settings(database=path, development_mode=True)
    return TestClient(create_app(settings))


def _database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        initialize(connection)
        write_quarter(
            connection,
            (
                "electricity",
                "2024T4",
                "package",
                "resource",
                "2025-08-01",
                4,
                "now",
                "source",
                "CC-BY-SA-4.0",
                "https://creativecommons.org/licenses/by-sa/4.0/",
                CONDITIONS_URL,
                ATTRIBUTION,
            ),
            [
                ("electricity", "2024T4", 1, "R1-001", "Red", "R2-001", "Com A", "marketer", "2.0TD", "13", 70, 700),
                ("electricity", "2024T4", 2, "R1-001", "Red", "R2-002", "Com B", "marketer", "2.0TD", "13", 30, 300),
                ("electricity", "2024T4", 3, "R1-001", "Red", None, None, "direct_consumer", "2.0TD", "13", 5, 50),
                ("electricity", "2024T4", 4, "R1-001", "Red", None, None, "unavailable", "2.0TD", "01", 2, 20),
            ],
        )


def test_read_only_connection_can_move_between_request_workers(tmp_path: Path) -> None:
    database = tmp_path / "market.sqlite"
    _database(database)
    request = Request({"type": "http", "app": _client(database).app})

    with closing(get_session(request)) as dependency, ThreadPoolExecutor(max_workers=1) as worker:
        session = next(dependency)
        connection = session.connection()

        def read_from_worker() -> int:
            assert session.scalar(text("PRAGMA query_only")) == 1
            with pytest.raises(OperationalError, match="readonly"):
                session.execute(text("DELETE FROM market_rows"))
            return session.scalar(text("SELECT SUM(supplies) FROM market_rows"))

        assert worker.submit(read_from_worker).result(timeout=5) == 107
        worker.submit(dependency.close).result(timeout=5)

    assert connection.closed


def test_shares_use_registered_marketer_denominator(tmp_path: Path) -> None:
    database = tmp_path / "market.sqlite"
    _database(database)
    client = _client(database)
    response = client.get("/v1/market/shares?period=2024T4&community_code=13&limit=1")

    assert response.status_code == 200
    data = response.json()
    assert data["marketer_supplies"] == 100
    assert data["direct_consumer_supplies"] == 5
    assert data["unavailable_supplies"] == 0
    assert data["items"] == [{"marketer_code": "R2-001", "observed_name": "Com A", "supplies": 70, "share": 0.7}]
    assert data["metadata_modified"] == "2025-08-01"
    assert client.get("/v1/market/shares?period=2024T4&limit=101").status_code == 422
    assert client.get("/v1/market/shares?period=2024T4&community_code=99").status_code == 422


def test_quarters_and_series(tmp_path: Path) -> None:
    database = tmp_path / "market.sqlite"
    _database(database)
    client = _client(database)
    quarters = client.get("/v1/market/quarters")
    series = client.get("/v1/market/series/R2-001?community_code=13")

    assert quarters.status_code == 200
    assert quarters.json()["quarters"][0]["row_count"] == 4
    assert series.status_code == 200
    assert series.json()["series"] == [{"period": "2024T4", "supplies": 70, "metadata_modified": "2025-08-01"}]
    assert series.json()["attribution"] == ATTRIBUTION
    assert client.get("/v1/market/series/R2-000").status_code == 422


def test_missing_database_returns_service_unavailable() -> None:
    assert _client(None).get("/v1/market/quarters").status_code == 503


def test_community_map_distinguishes_zero_share_from_missing_denominator(tmp_path: Path) -> None:
    database = tmp_path / "market.sqlite"
    _database(database)
    client = _client(database)
    data = client.get("/v1/market/communities/R2-001?period=2024T4").json()
    assert data["denominator"] == "supplies_with_registered_marketer"
    assert data["metadata_modified"] == "2025-08-01"
    madrid = next(row for row in data["items"] if row["community_code"] == "13")
    assert madrid["share"] == 0.7
    assert madrid["direct_consumer_supplies"] == 5
    andalusia = next(row for row in data["items"] if row["community_code"] == "01")
    assert andalusia["share"] is None
    assert andalusia["unavailable_supplies"] == 2
    absent = client.get("/v1/market/communities/R2-999?period=2024T4").json()
    assert next(row for row in absent["items"] if row["community_code"] == "13")["share"] == 0
    assert client.get("/v1/market/communities/R2-000?period=2024T4").status_code == 422
    assert client.get("/v1/market/communities/R2-001?period=2025T4").status_code == 404
    assert client.get("/v1/market/communities/R2-001?period=invalid").status_code == 422
    assert client.get("/v1/market/communities/R2-001?period=2024T4&sector=gas").status_code == 404


@pytest.fixture
def series_database(tmp_path: Path) -> Path:
    database = tmp_path / "market.sqlite"
    _database(database)
    with sqlite3.connect(database) as connection:
        template = connection.execute("SELECT * FROM loads_view WHERE period='2024T4'").fetchone()
        extra_rows = {
            "2024T2": (
                "electricity",
                "2024T2",
                1,
                "R1-001",
                "Red",
                None,
                None,
                "direct_consumer",
                "2.0TD",
                "13",
                9,
                90,
            ),
            "2024T3": (
                "electricity",
                "2024T3",
                1,
                "R1-001",
                "Red",
                "R2-002",
                "Com B",
                "marketer",
                "2.0TD",
                "13",
                10,
                100,
            ),
            "2025T1": (
                "electricity",
                "2025T1",
                1,
                "R1-001",
                "Red",
                "R2-001",
                "Consumidor Directo",
                "marketer",
                "2.0TD",
                "01",
                20,
                200,
            ),
        }
        for period in ("2025T1", "2024T2", "2024T3"):
            load = (
                template[0],
                period,
                f"package-{period}",
                f"resource-{period}",
                f"revision-{period}",
                1,
                template[6],
                f"source-{period}",
                *template[8:],
            )
            write_quarter(connection, load, [extra_rows[period]])
    return database


def test_share_series_order_totals_and_period_metadata(series_database: Path) -> None:
    data = _client(series_database).get("/v1/market/share-series/R2-001").json()
    assert data["sector"] == "electricity"
    assert data["marketer_code"] == "R2-001"
    assert data["community_code"] is None
    assert data["denominator"] == "supplies_with_registered_marketer"
    points = data["series"]
    assert [point["period"] for point in points] == ["2024T2", "2024T3", "2024T4", "2025T1"]
    assert [point["supplies"] for point in points] == [0, 0, 70, 20]
    assert [point["marketer_supplies"] for point in points] == [0, 10, 100, 20]
    assert [point["share"] for point in points] == [None, 0.0, 0.7, 1.0]
    assert [point["direct_consumer_supplies"] for point in points] == [9, 0, 5, 0]
    assert [point["unavailable_supplies"] for point in points] == [0, 0, 2, 0]
    for point in points:
        assert point["license_id"] == "CC-BY-SA-4.0"
        assert point["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
        assert point["conditions_url"] == CONDITIONS_URL
        assert point["attribution"] == ATTRIBUTION
        if point["period"] != "2024T4":
            for field, prefix in (
                ("package_name", "package"),
                ("resource_id", "resource"),
                ("metadata_modified", "revision"),
                ("source_url", "source"),
            ):
                assert point[field] == f"{prefix}-{point['period']}"


def test_share_series_filters_and_absent_codes(series_database: Path) -> None:
    client = _client(series_database)
    points = client.get("/v1/market/share-series/R2-001?community_code=13").json()["series"]
    assert [point["share"] for point in points] == [None, 0.0, 0.7, None]
    assert points[-1]["supplies"] == points[-1]["marketer_supplies"] == 0
    points = client.get("/v1/market/share-series/R2-999").json()["series"]
    assert [point["share"] for point in points] == [None, 0.0, 0.0, 0.0]
    assert all(point["supplies"] == 0 for point in points)
    assert client.get("/v1/market/share-series/R2-001?sector=gas").json()["series"] == []
    assert client.get("/v1/market/share-series/R2-001?start_period=2026T1").json()["series"] == []
    selected = client.get("/v1/market/share-series/R2-001?start_period=2024T3&end_period=2024T4").json()["series"]
    assert [point["period"] for point in selected] == ["2024T3", "2024T4"]
    assert client.get("/v1/market/share-series/R2-001?limit=1&offset=1").json()["series"] == selected[:1]


@pytest.mark.parametrize(
    "suffix",
    [
        "R2-000",
        "Consumidor%20Directo",
        "R1-001",
        "R2-001?community_code=1",
        "R2-001?community_code=99",
        "R2-001?sector=invalid",
        "R2-001?start_period=2024T0",
        "R2-001?end_period=invalid",
        "R2-001?start_period=2025T1&end_period=2024T4",
        "R2-001?limit=0",
        "R2-001?limit=121",
        "R2-001?offset=-1",
        "R2-001?offset=10001",
    ],
)
def test_share_series_rejects_invalid_bounds(series_database: Path, suffix: str) -> None:
    assert _client(series_database).get(f"/v1/market/share-series/{suffix}").status_code == 422


def test_share_series_caps_loaded_quarters(series_database: Path) -> None:
    with sqlite3.connect(series_database) as connection:
        template = connection.execute("SELECT * FROM loads_view WHERE period='2024T4'").fetchone()
        existing = {row[0] for row in connection.execute("SELECT period FROM loads_view")}
        for year in range(2000, 2031):
            for quarter in range(1, 5):
                period = f"{year}T{quarter}"
                if period not in existing:
                    write_quarter(connection, (template[0], period, *template[2:5], 0, *template[6:]), [])
    client = _client(series_database)
    first = client.get("/v1/market/share-series/R2-001").json()["series"]
    rest = client.get("/v1/market/share-series/R2-001?offset=120").json()["series"]
    assert len(first) == 120
    assert first[0]["period"] == "2000T1"
    assert first[-1]["period"] == "2029T4"
    assert [point["period"] for point in rest] == ["2030T1", "2030T2", "2030T3", "2030T4"]


def test_share_series_uses_shared_ip_quota(series_database: Path) -> None:
    settings = Settings(request_limit=1, database=series_database)
    app = create_app(settings)
    # Exercise production quotas with a local fixture instead of a live Turso account.
    app.state.database_engine = create_database_engine(series_database)
    client = TestClient(app)
    url = "/v1/market/share-series/R2-001"
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "1"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert client.get("/v1/market/quarters").status_code == 429
    assert client.get(url).headers["Retry-After"]
    assert client.get("/v1/distribution/provinces").status_code == 429


def test_share_series_database_unavailable() -> None:
    assert _client(None).get("/v1/market/share-series/R2-001").status_code == 503


def test_share_series_preserves_repeated_rows_and_reads_revisions(series_database: Path) -> None:
    client = _client(series_database)
    url = "/v1/market/share-series/R2-001?start_period=2024T4&end_period=2024T4"
    assert client.get(url).json()["series"][0]["supplies"] == 70
    with sqlite3.connect(series_database) as connection:
        connection.execute(
            """INSERT INTO market_rows SELECT load_id, 5, distributor_name_id, marketer_name_id,
               category, tariff_id, community_code, supplies, energy_kwh
               FROM market_rows WHERE load_id=1 AND source_row_id=1"""
        )
        connection.execute("UPDATE loads SET metadata_modified='revised' WHERE id=1")
    point = client.get(url).json()["series"][0]
    assert point["supplies"] == 140
    assert point["marketer_supplies"] == 170
    assert point["share"] == 140 / 170
    assert point["metadata_modified"] == "revised"
    # The old route retains its supplies-only shape and only observed quarters.
    legacy = client.get("/v1/market/series/R2-001").json()["series"]
    assert legacy == [
        {"period": "2024T4", "supplies": 140, "metadata_modified": "revised"},
        {"period": "2025T1", "supplies": 20, "metadata_modified": "revision-2025T1"},
    ]


@pytest.mark.parametrize(
    "url",
    [
        "/v1/market/quarters?unexpected=true",
        "/v1/market/shares?period=2024T4&unexpected=true",
        "/v1/market/series/R2-001?unexpected=true",
        "/v1/market/share-series/R2-001?unexpected=true",
        "/v1/market/communities/R2-001?period=2024T4&unexpected=true",
        "/v1/market/shares",
        "/v1/market/shares?period=2024T4&limit=1.5",
        "/v1/market/shares?period=2024T4&offset=-1",
        "/v1/market/shares?period=2024T4&offset=10001",
        "/v1/market/quarters?sector=unknown",
        "/v1/market/series/R2-001?community_code=00",
        "/v1/market/series/R2-001?community_code=20",
        "/v1/market/series/R2-001?community_code=01%0A",
        "/v1/market/series/R2-001%0A",
        "/v1/market/shares?period=2024T4%0A",
        "/v1/market/series/R2-%D9%A1",
    ],
)
def test_request_dtos_reject_invalid_or_extra_parameters(series_database: Path, url: str) -> None:
    response = _client(series_database).get(url)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert isinstance(errors, list) and errors
    assert all(set(error) == {"loc", "msg", "type"} for error in errors)
    if "unexpected" in url:
        assert errors[0]["type"] == "extra_forbidden"
        assert errors[0]["loc"] == ["query", "unexpected"]


def test_orm_matches_ingestion_schema_and_preserves_source_identity(series_database: Path) -> None:
    client = _client(series_database)
    inspector = inspect(client.app.state.database_engine)
    for model in (MarketLoad, MarketRow):
        columns = inspector.get_columns(model.__tablename__)
        assert {column["name"] for column in columns} == set(model.__table__.columns.keys())
        assert model.__tablename__ in inspector.get_view_names()
    assert inspector.get_pk_constraint("market_rows")["constrained_columns"] == ["load_id", "source_row_id"]
    assert {fk["referred_table"] for fk in inspector.get_foreign_keys("market_rows")} == {
        "loads",
        "company_names",
        "tariffs",
        "communities",
    }
    request = Request({"type": "http", "app": client.app})
    with closing(get_session(request)) as dependency:
        session = next(dependency)
        load = session.get(MarketLoad, ("electricity", "2024T4"))
        assert load.resource_id == "resource"
        row = session.scalars(select(MarketRow).where(MarketRow.period == "2024T4", MarketRow.source_id == 3)).one()
        assert row.marketer_code is None
        assert row.category == "direct_consumer"


def test_concurrent_requests_have_independent_sessions(series_database: Path) -> None:
    client = _client(series_database)
    urls = [
        "/v1/market/quarters",
        "/v1/market/shares?period=2024T4",
        "/v1/market/series/R2-001",
        "/v1/market/share-series/R2-001",
        "/v1/market/communities/R2-001?period=2024T4",
    ]
    expected = {url: client.get(url).json() for url in urls}
    with ThreadPoolExecutor(max_workers=5) as workers:
        results = list(workers.map(client.get, urls * 3))
    for url, response in zip(urls * 3, results, strict=True):
        assert response.status_code == 200
        assert response.json() == expected[url]


def test_missing_database_is_not_created(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite"
    assert _client(path).get("/v1/market/quarters").status_code == 503
    assert not path.exists()


def test_sqlite_uri_preserves_special_characters_in_file_path(tmp_path: Path) -> None:
    path = tmp_path / "market ?#%.sqlite"
    _database(path)
    response = _client(path).get("/v1/market/shares?period=2024T4")
    assert response.status_code == 200
    assert response.json()["marketer_supplies"] == 100


def test_request_transaction_keeps_data_and_metadata_on_same_revision(series_database: Path) -> None:
    with sqlite3.connect(series_database) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        client = _client(series_database)
        request = Request({"type": "http", "app": client.app})
        revision = select(MarketLoad.metadata_modified).where(MarketLoad.period == "2024T4")
        supplies = select(MarketRow.supplies).where(MarketRow.period == "2024T4", MarketRow.source_id == 1)
        with closing(get_session(request)) as dependency:
            session = next(dependency)
            assert session.scalar(revision) == "2025-08-01"
            writer.execute("UPDATE loads SET metadata_modified='revised' WHERE id=1")
            writer.execute("UPDATE market_rows SET supplies=140 WHERE load_id=1 AND source_row_id=1")
            writer.commit()
            assert session.scalar(supplies) == 70
            assert session.scalar(revision) == "2025-08-01"
        with closing(get_session(request)) as dependency:
            session = next(dependency)
            assert session.scalar(supplies) == 140
            assert session.scalar(revision) == "revised"


def test_database_without_market_schema_returns_documented_error(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER)")
    response = _client(path).get("/v1/market/quarters")
    assert response.status_code == 503
    assert response.json() == {"detail": "Market database is unavailable"}


def test_response_dtos_keep_nullable_names_and_omit_internal_fields(series_database: Path) -> None:
    with sqlite3.connect(series_database) as connection:
        name_id = connection.execute(
            "INSERT INTO company_names (company_id, name) "
            "SELECT id, NULL FROM companies WHERE code='R2-001' RETURNING id"
        ).fetchone()[0]
        connection.execute(
            """UPDATE market_rows SET marketer_name_id=? WHERE marketer_name_id IN
               (SELECT n.id FROM company_names n JOIN companies c ON c.id=n.company_id WHERE c.code='R2-001')""",
            (name_id,),
        )
    client = _client(series_database)
    quarters = client.get("/v1/market/quarters").json()["quarters"]
    assert all("loaded_at" not in quarter and "sector" not in quarter for quarter in quarters)
    item = client.get("/v1/market/shares?period=2024T4").json()["items"][0]
    assert item == {"marketer_code": "R2-001", "observed_name": None, "supplies": 70, "share": 0.7}
    gas = client.get("/v1/market/series/R2-001?sector=gas").json()
    assert gas["series"] == []
    assert all(
        gas[field] is None for field in ("source_url", "license_id", "license_url", "conditions_url", "attribution")
    )

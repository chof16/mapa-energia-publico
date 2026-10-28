"""PostgreSQL configuration and synthetic cross-database API contracts."""

import os
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from electricity_map_api.config import Settings
from electricity_map_api.main import create_app
from electricity_map_ingestion import gas_distribution_store
from electricity_map_ingestion.electricity_store import initialize, write_quarter
from electricity_map_ingestion.gas_distribution import NetworkRow
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from scripts.export_database import _ordered_dump


@pytest.mark.parametrize("environment", ["development", "production"])
def test_postgres_configuration_takes_precedence(monkeypatch: pytest.MonkeyPatch, environment: str) -> None:
    monkeypatch.setenv("ENV", environment)
    monkeypatch.setenv("MAPA_DATABASE", "unused.sqlite")
    monkeypatch.setenv("MAPA_DATABASE_URL", "postgresql://user:secret@example.org/mapa?sslmode=require")
    settings = Settings.from_environment()
    assert settings.database is None
    assert settings.database_url is not None
    assert "secret" not in repr(settings)
    app = create_app(settings)
    assert app.state.database_engine.dialect.name == "postgresql"
    app.state.database_engine.dispose()


@pytest.mark.parametrize(
    "url",
    ["secret", "sqlite:///secret", "postgresql:///secret", "postgresql://host", "postgresql://host:secret/db"],
)
def test_invalid_postgres_url_hides_credentials(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("MAPA_DATABASE_URL", url)
    with pytest.raises(ValueError, match="MAPA_DATABASE_URL") as error:
        Settings.from_environment()
    assert "secret" not in str(error.value)


def test_sqlite_setting_rejects_connection_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("MAPA_DATABASE_URL", raising=False)
    monkeypatch.setenv("MAPA_DATABASE", "postgresql://user:secret@example.org/mapa")
    with pytest.raises(ValueError, match="use MAPA_DATABASE_URL") as error:
        Settings.from_environment()
    assert "secret" not in str(error.value)


def test_postgres_matches_sqlite_and_forbids_writes(tmp_path: Path) -> None:
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set TEST_POSTGRES_URL to run the isolated PostgreSQL integration test")
    database = tmp_path / "synthetic.sqlite"
    with sqlite3.connect(database) as source:
        initialize(source)
        for period in ("2024T4", "2025T1"):
            write_quarter(
                source,
                (
                    "electricity",
                    period,
                    "package",
                    "resource",
                    "revision",
                    4,
                    "now",
                    "source",
                    "license",
                    "license-url",
                    "conditions",
                    "attribution",
                ),
                [
                    (
                        "electricity",
                        period,
                        1,
                        "R1-001",
                        "Red",
                        "R2-001",
                        "Com A",
                        "marketer",
                        "2.0TD",
                        "13",
                        70,
                        7_000_000_000,
                    ),
                    ("electricity", period, 2, "R1-001", "Red", "R2-001", "Com A", "marketer", "2.0TD", "13", 70, -10),
                    ("electricity", period, 3, "R1-001", "Red", None, None, "direct_consumer", "2.0TD", "01", 5, 50),
                    ("electricity", period, 4, "R1-001", "Red", None, None, "unavailable", "2.0TD", "01", 2, 20),
                ],
            )
        gas_distribution_store.initialize(source)
        gas_distribution_store.write_load(
            source,
            [
                NetworkRow(4, "01", "Synthetic municipality", "Synthetic distributor SA", 7_000_000_000),
                NetworkRow(5, "01", "Synthetic municipality", "Synthetic distributor SA", 0),
            ],
            "a" * 64,
        )
        source.commit()
        # Use only trusted schema and synthetic rows, never a downloaded database.
        statements = [
            statement.replace("INTEGER", "BIGINT").replace(
                "printf('%04dT%d', p.year, p.quarter)", "(p.year::text || 'T' || p.quarter::text)"
            )
            for statement in _ordered_dump(source)
            if statement not in {"BEGIN TRANSACTION;", "COMMIT;"}
        ]
    schema = "test_" + uuid4().hex
    admin = create_engine(make_url(url).set(drivername="postgresql+psycopg"))
    remote = create_app(Settings(database_url=url, development_mode=True))
    local = create_app(Settings(database=database, development_mode=True))
    try:
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            for statement in statements:
                connection.exec_driver_sql(statement)

        @event.listens_for(remote.state.database_engine, "begin")
        def select_test_schema(connection) -> None:
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')

        with TestClient(remote) as postgres, TestClient(local) as sqlite:
            for path in (
                "/v1/market/quarters",
                "/v1/electricity/quarters",
                "/v1/electricity/shares?period=2024T4",
                "/v1/market/shares?period=2024T4",
                "/v1/market/shares?period=2024T4&community_code=01",
                "/v1/market/series/R2-001",
                "/v1/market/share-series/R2-001",
                "/v1/market/share-series/R2-001?community_code=01",
                "/v1/market/share-series/R2-999",
                "/v1/market/communities/R2-001?period=2024T4",
                "/v1/gas/distribution/provinces",
                "/v1/gas/distribution/provinces/01",
                "/v1/gas/distribution/provinces/35",
                "/v1/gas/distribution/revisions",
            ):
                actual, expected = postgres.get(path), sqlite.get(path)
                assert actual.status_code == expected.status_code == 200
                assert actual.json() == expected.json()
            with remote.state.database_engine.connect() as connection:
                assert connection.scalar(text("SHOW transaction_read_only")) == "on"
                assert connection.scalar(text("SHOW transaction_isolation")) == "repeatable read"
                with pytest.raises(DBAPIError) as error:
                    connection.exec_driver_sql("DELETE FROM market_rows")
                assert error.value.orig.sqlstate == "25006"
    finally:
        remote.state.database_engine.dispose()
        local.state.database_engine.dispose()
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        admin.dispose()

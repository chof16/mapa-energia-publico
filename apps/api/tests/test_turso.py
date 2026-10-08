"""Remote TursoDB wiring exercised against SQLite with the same DB-API contract."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import turso_serverless
from electricity_map_api.config import Settings
from electricity_map_api.distribution.store import build_database
from electricity_map_api.main import create_app
from electricity_map_ingestion.cnmc_market import ATTRIBUTION, CONDITIONS_URL
from electricity_map_ingestion.market_store import initialize, write_quarter
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from turso_serverless.session import StmtResult


def test_one_remote_database_serves_market_and_distribution_without_local_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    market_path = tmp_path / "market.sqlite"
    with sqlite3.connect(market_path) as connection:
        initialize(connection)
        write_quarter(
            connection,
            (
                "electricity",
                "2024T4",
                "package",
                "resource",
                "2025-08-01",
                1,
                "now",
                "source",
                "CC-BY-SA-4.0",
                "https://creativecommons.org/licenses/by-sa/4.0/",
                CONDITIONS_URL,
                ATTRIBUTION,
            ),
            [("electricity", "2024T4", 1, "R1-001", "Red", "R2-001", "Com A", "marketer", "2.0TD", "13", 70, 700)],
        )
    build_database(market_path)
    connections: list[str] = []

    class LocalSession:
        def __init__(self, path: Path) -> None:
            self.connection = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
            # Model the remote read-only token without sending a forbidden PRAGMA.
            self.connection.execute("PRAGMA query_only=ON")

        @property
        def autocommit(self) -> bool:
            return not self.connection.in_transaction

        def execute_stmt(self, sql, *, args=None, named_args=None, want_rows=True):
            assert "query_only" not in sql.lower()
            parameters = {name.lstrip(":$@"): value for name, value in named_args} if named_args else args or []
            try:
                cursor = self.connection.execute(sql, parameters)
            except sqlite3.Error as error:
                raise RuntimeError(str(error)) from error
            columns = [item[0] for item in cursor.description] if cursor.description else []
            rows = cursor.fetchall() if columns and want_rows else []
            return StmtResult(columns, rows, cursor.rowcount, cursor.lastrowid)

        def close(self) -> None:
            self.connection.close()

    def local_turso_connection(url: str, *, auth_token: str, isolation_level: str | None):
        assert url == "turso://combined.example"
        assert auth_token == "secret"
        assert isolation_level is None
        connections.append(url)
        return turso_serverless.Connection(LocalSession(market_path), isolation_level=isolation_level)

    monkeypatch.setattr(turso_serverless, "connect", local_turso_connection)
    settings = Settings(
        database=tmp_path / "missing.sqlite",
        turso_url="turso://combined.example",
        turso_auth_token="secret",
        cors_origins=("https://map.example",),
    )
    app = create_app(settings)
    client = TestClient(app)
    market = client.get("/v1/market/quarters")
    shares = client.get("/v1/market/shares?period=2024T4&community_code=13")
    distribution = client.get("/v1/distribution/provinces?sector=electricity")
    assert market.status_code == 200
    assert market.json()["quarters"][0]["row_count"] == 1
    assert shares.status_code == 200
    assert shares.json()["marketer_supplies"] == 70
    assert distribution.status_code == 200
    preflight = client.options(
        "/v1/market/quarters",
        headers={"Origin": "https://map.example", "Access-Control-Request-Method": "GET"},
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://map.example"
    assert (
        "access-control-allow-origin"
        not in client.get("/v1/market/quarters", headers={"Origin": "https://unknown.example"}).headers
    )
    assert connections and set(connections) == {"turso://combined.example"}

    with app.state.database_engine.connect() as connection:
        with pytest.raises(OperationalError, match="readonly"):
            connection.execute(text("DELETE FROM market_rows"))


def test_turso_environment_requires_url_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("MAPA_TURSO_URL", "turso://combined.example")
    monkeypatch.delenv("MAPA_TURSO_AUTH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="must be set together"):
        Settings.from_environment()
    monkeypatch.setenv("MAPA_TURSO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("MAPA_TURSO_URL", "http://wrong.example")
    with pytest.raises(ValueError, match="must use turso://, libsql:// or https://"):
        Settings.from_environment()


@pytest.mark.parametrize("scheme", ["turso", "libsql", "https"])
def test_supported_remote_url_schemes(monkeypatch: pytest.MonkeyPatch, scheme: str) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("MAPA_TURSO_URL", f"{scheme}://combined.example")
    monkeypatch.setenv("MAPA_TURSO_AUTH_TOKEN", "secret")
    settings = Settings.from_environment()
    assert settings.turso_url == f"{scheme}://combined.example"
    assert settings.turso_auth_token == "secret"
    assert "secret" not in repr(settings)


@pytest.mark.parametrize(
    "url",
    [
        "libsql://user:secret@combined.example",
        "https://combined.example?token=secret",
        "turso://combined.example#secret",
        "https://combined.example/v3/pipeline",
        "libsql:///missing-host",
    ],
)
def test_remote_url_rejects_embedded_credentials_and_paths(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("MAPA_TURSO_URL", url)
    monkeypatch.setenv("MAPA_TURSO_AUTH_TOKEN", "secret")
    with pytest.raises(ValueError, match="MAPA_TURSO_URL") as error:
        Settings.from_environment()
    assert "secret" not in str(error.value)

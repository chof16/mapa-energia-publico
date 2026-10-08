"""One database preserves independent datasets through refreshes and exports."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from electricity_map_api.config import Settings
from electricity_map_api.distribution.store import build_database, load_manifest
from electricity_map_api.main import create_app
from electricity_map_ingestion.market_store import initialize, write_quarter
from fastapi.testclient import TestClient

from scripts.build_combined_database import build
from scripts.export_database import prepare, prepare_sql_dump


def test_environment_uses_one_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    database = tmp_path / "mapa.sqlite"
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("MAPA_DATABASE", str(database))
    settings = Settings.from_environment()
    assert settings.database == database
    build_database(database)
    with closing(sqlite3.connect(database)) as connection:
        initialize(connection)
    with TestClient(create_app(settings)) as client:
        assert client.get("/v1/market/quarters").status_code == 200
        assert client.get("/v1/distribution/provinces").status_code == 200


def test_environment_selects_backend_without_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    database = tmp_path / "mapa.sqlite"
    build_database(database)
    monkeypatch.setenv("MAPA_DATABASE", str(database))
    monkeypatch.setenv("MAPA_TURSO_URL", "turso://example")
    monkeypatch.setenv("MAPA_TURSO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("ENV", "development")
    local = Settings.from_environment()
    assert local.database == database
    assert local.turso_url is None
    assert local.turso_auth_token is None
    monkeypatch.setenv("ENV", "production")
    remote = Settings.from_environment()
    assert remote.database is None
    assert remote.turso_url == "turso://example"
    assert "secret" not in repr(remote)
    monkeypatch.delenv("MAPA_TURSO_URL")
    monkeypatch.delenv("MAPA_TURSO_AUTH_TOKEN")
    with TestClient(create_app(Settings.from_environment())) as client:
        assert client.get("/v1/distribution/provinces").status_code == 503


def test_distribution_skips_unchanged_tables_and_preserves_market(tmp_path: Path) -> None:
    database = tmp_path / "mapa.sqlite"
    build_database(database)
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(
            "CREATE TABLE market_marker (value TEXT); INSERT INTO market_marker VALUES ('preserved');"
            "CREATE TRIGGER unchanged_identity BEFORE DELETE ON distributor_identity "
            "BEGIN SELECT RAISE(ABORT, 'identity must not be rewritten'); END;"
        )
    before = database.read_bytes()
    build_database(database)
    assert database.read_bytes() == before
    manifest = load_manifest()
    manifest["claims"][0]["decision_reason"] = "Updated review reason"
    build_database(database, manifest)
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT value FROM market_marker").fetchone() == ("preserved",)
        assert connection.execute(
            "SELECT decision_reason FROM claim_decision WHERE id=?", (manifest["claims"][0]["id"],)
        ).fetchone() == ("Updated review reason",)


def test_distribution_write_failure_rolls_back_all_changed_tables(tmp_path: Path) -> None:
    database = tmp_path / "mapa.sqlite"
    build_database(database)
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(
            "CREATE TRIGGER fail_claim BEFORE INSERT ON claim_decision "
            "BEGIN SELECT RAISE(ABORT, 'simulated failure'); END;"
        )
    before = database.read_bytes()
    manifest = load_manifest()
    manifest["snapshot_date"] = "2026-10-08"
    manifest["claims"][0]["decision_reason"] = "Changed"
    with pytest.raises(sqlite3.IntegrityError, match="simulated failure"):
        build_database(database, manifest)
    assert database.read_bytes() == before


def test_combined_builder_and_exports_preserve_source_and_refuse_reinitialization(tmp_path: Path) -> None:
    source = tmp_path / "market.sqlite"
    database = tmp_path / "mapa.sqlite"
    with closing(sqlite3.connect(source)) as connection:
        initialize(connection)
        with connection:
            write_quarter(
                connection,
                (
                    "electricity",
                    "2025T4",
                    "package",
                    "resource",
                    "revision",
                    1,
                    "now",
                    "source",
                    "CC-BY-SA-4.0",
                    "license-url",
                    "conditions",
                    "attribution",
                ),
                [("electricity", "2025T4", 1, "R1-001", "Red", "R2-001", "Com", "marketer", "2.0TD", "13", 1, 2)],
            )
    original = source.read_bytes()
    result = build(source, database)
    assert result["market_rows"] == 1
    assert result["decisions"] == {"accepted": 59, "rejected": 4}
    assert result["journal_mode"] == "wal"
    assert source.read_bytes() == original
    with pytest.raises(ValueError, match="already exists"):
        build(source, database)
    upload = tmp_path / "upload" / "mapa.sqlite"
    assert prepare(database, upload, "combined")["market_rows"] == 1
    assert not list(upload.parent.glob(".*.sqlite-*"))
    export = upload.with_suffix(".sql")
    assert prepare_sql_dump(upload, export, "combined")["statements"] > 0


def test_builder_rejects_non_sqlite_before_opening(tmp_path: Path) -> None:
    source = tmp_path / "fake.sqlite"
    source.write_text('{"not": "sqlite"}')
    destination = tmp_path / "mapa.sqlite"
    with pytest.raises(ValueError, match="Invalid SQLite header"):
        build(source, destination)
    assert not destination.exists()

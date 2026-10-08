"""Publication tests use synthetic CNMC quarters and real SQLite files."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from electricity_map_ingestion import cnmc_market, market_store, refresh_cnmc_market


def _package(period: str, revision: str = "revision-1") -> dict:
    return {
        "title": f"Mercado minorista de electricidad {period}",
        "name": f"ds_{period}",
        "license_id": "CC-BY-SA-4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "metadata_modified": revision,
        "extras": [{"key": "periodo", "value": period}],
        "resources": [{"position": 0, "datastore_active": True, "id": f"resource-{period}"}],
    }


def _row(period: str, source_id: int, **changes: object) -> dict:
    row = {
        "_id": source_id,
        "fecha": period,
        "anno_envio": period[:4],
        "trimestre_envio": period[-2:],
        "cod_dis": "R1-001",
        "descripcion_distribuidor": "Red, S.A.",
        "cod_com": "R2-004",
        "descripcion_comercializador": "Comercial, S.A.",
        "tarifa_acceso": "2.0TD",
        "ccaa": "Madrid, Comunidad de",
        "numero_suministro": 2,
        "energia": -294,
    }
    row.update(changes)
    return row


def _source(monkeypatch: pytest.MonkeyPatch, packages: dict, rows: dict) -> None:
    monkeypatch.setattr(cnmc_market, "discover", lambda: packages)
    monkeypatch.setattr(cnmc_market, "online_rows", lambda resource: iter(rows[resource]))


def _loads(path: Path) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT period, metadata_modified, row_count FROM loads_view ORDER BY period"
        ).fetchall()


def test_unchanged_catalog_does_not_replace_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "market.sqlite"
    package = _package("2024T4")
    _source(monkeypatch, {"2024T4": package}, {"resource-2024T4": [_row("2024T4", 1)]})
    assert refresh_cnmc_market.refresh(database) == [("2024T4", 1)]
    before = database.stat()
    monkeypatch.setattr(cnmc_market, "online_rows", lambda resource: pytest.fail("Downloaded unchanged quarter"))
    assert refresh_cnmc_market.refresh(database) == []
    after = database.stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)


def test_new_quarter_publishes_complete_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "market.sqlite"
    first = _package("2024T4")
    second = _package("2025T1")
    rows = {
        "resource-2024T4": [_row("2024T4", 1)],
        "resource-2025T1": [_row("2025T1", 1), _row("2025T1", 2)],
    }
    _source(monkeypatch, {"2024T4": first}, rows)
    refresh_cnmc_market.refresh(database)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE coverage_marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO coverage_marker VALUES ('preserved')")
    inode = database.stat().st_ino
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as reader:
        reader.execute("BEGIN")
        assert reader.execute("SELECT COUNT(*) FROM loads").fetchone() == (1,)
        _source(monkeypatch, {"2024T4": first, "2025T1": second}, rows)
        assert refresh_cnmc_market.refresh(database) == [("2025T1", 2)]
        assert reader.execute("SELECT COUNT(*) FROM loads").fetchone() == (1,)
    assert _loads(database) == [("2024T4", "revision-1", 1), ("2025T1", "revision-1", 2)]
    assert database.stat().st_ino == inode
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM coverage_marker").fetchone() == ("preserved",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute(
            "SELECT source_id, energy_kwh FROM market_rows_view WHERE period='2025T1' ORDER BY source_id"
        ).fetchall() == [(1, -294), (2, -294)]
        assert connection.execute(
            "SELECT license_id, attribution FROM loads_view WHERE period='2025T1'"
        ).fetchone() == (
            "CC-BY-SA-4.0",
            cnmc_market.ATTRIBUTION,
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM ingestion_issues_view WHERE period='2025T1' AND kind='repeated_identical_key'"
        ).fetchone() == (1,)


def test_revised_quarter_replaces_only_its_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "market.sqlite"
    rows = {"resource-2024T4": [_row("2024T4", 1)], "resource-2025T1": [_row("2025T1", 1)]}
    _source(monkeypatch, {"2024T4": _package("2024T4"), "2025T1": _package("2025T1")}, rows)
    refresh_cnmc_market.refresh(database)
    rows["resource-2024T4"] = [_row("2024T4", 8, energia=8)]
    _source(monkeypatch, {"2024T4": _package("2024T4", "revision-2"), "2025T1": _package("2025T1")}, rows)
    assert refresh_cnmc_market.refresh(database) == [("2024T4", 1)]
    assert _loads(database) == [("2024T4", "revision-2", 1), ("2025T1", "revision-1", 1)]
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT source_id, energy_kwh FROM market_rows_view WHERE period='2024T4'"
        ).fetchall() == [(8, 8)]


@pytest.mark.parametrize("failure", ["row", "download", "metadata", "database"])
def test_failure_leaves_old_database_readable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    database = tmp_path / "market.sqlite"
    rows = {"resource-2024T4": [_row("2024T4", 1)], "resource-2025T1": [_row("2025T1", 1)]}
    _source(monkeypatch, {"2024T4": _package("2024T4")}, rows)
    refresh_cnmc_market.refresh(database)
    before = database.stat()
    packages = {"2024T4": _package("2024T4"), "2025T1": _package("2025T1")}
    _source(monkeypatch, packages, rows)
    if failure == "row":
        rows["resource-2025T1"] = [_row("2025T1", 1, ccaa="Unknown")]
    elif failure == "download":
        monkeypatch.setattr(cnmc_market, "online_rows", lambda resource: (_ for _ in ()).throw(OSError("network")))
    elif failure == "metadata":
        calls = 0

        def changing_catalog() -> dict:
            nonlocal calls
            calls += 1
            return packages if calls == 1 else {**packages, "2025T1": _package("2025T1", "revision-2")}

        monkeypatch.setattr(cnmc_market, "discover", changing_catalog)
    else:
        monkeypatch.setattr(
            market_store,
            "validate_staged",
            lambda *args, **kwargs: (_ for _ in ()).throw(sqlite3.DatabaseError("integrity failure")),
        )
    with pytest.raises((ValueError, OSError, sqlite3.DatabaseError)):
        refresh_cnmc_market.refresh(database)
    assert database.stat().st_ino == before.st_ino
    assert _loads(database) == [("2024T4", "revision-1", 1)]
    assert list(tmp_path.glob("*.staging")) == []


def test_staged_count_validation_rejects_corruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "market.sqlite"
    rows = {"resource-2024T4": [_row("2024T4", 1)], "resource-2025T1": [_row("2025T1", 1)]}
    _source(monkeypatch, {"2024T4": _package("2024T4")}, rows)
    refresh_cnmc_market.refresh(database)
    before = database.stat()
    _source(monkeypatch, {"2024T4": _package("2024T4"), "2025T1": _package("2025T1")}, rows)
    original = cnmc_market.import_quarter

    def corrupt_count(connection: sqlite3.Connection, package: dict, rows: object, **kwargs) -> tuple[str, int, bool]:
        result = original(connection, package, rows, **kwargs)
        connection.execute("UPDATE loads SET row_count=99")
        connection.commit()
        return result

    monkeypatch.setattr(cnmc_market, "import_quarter", corrupt_count)
    with pytest.raises(ValueError, match="count mismatch"):
        refresh_cnmc_market.refresh(database)
    assert database.stat().st_ino == before.st_ino
    assert _loads(database) == [("2024T4", "revision-1", 1)]


def test_download_size_is_checked_before_json_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    class OversizedResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = {"Content-Type": "application/json", "Content-Length": "11"}

        def __enter__(self) -> OversizedResponse:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def read(self, size: int) -> bytes:
            pytest.fail("Oversized response body was read")

    monkeypatch.setattr(cnmc_market.urllib.request, "urlopen", lambda request, timeout: OversizedResponse())
    with pytest.raises(ValueError, match="Oversized response"):
        cnmc_market._fetch("package_search", {}, max_bytes=10)


def test_cached_json_size_is_checked_before_parse(tmp_path: Path) -> None:
    path = tmp_path / "source.json"
    path.write_bytes(b"{" + b" " * 10 + b"}")
    with pytest.raises(ValueError, match="oversized JSON file"):
        cnmc_market._read_json(path, 10)


def test_source_total_change_aborts_download(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = iter(
        [
            {"records": [_row("2025T1", 1)], "total": 2},
            {"records": [_row("2025T1", 2)], "total": 3},
        ]
    )
    monkeypatch.setattr(cnmc_market, "_fetch", lambda action, params: next(pages))
    with pytest.raises(ValueError, match="total changed"):
        list(cnmc_market.online_rows("resource-2025T1"))


def test_publish_failure_rolls_back_every_changed_quarter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "mapa.sqlite"
    periods = ("2024T4", "2025T1")
    rows = {f"resource-{period}": [_row(period, 1)] for period in periods}
    _source(monkeypatch, {period: _package(period) for period in periods}, rows)
    refresh_cnmc_market.refresh(database)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            "CREATE TRIGGER fail_second_quarter BEFORE INSERT ON market_rows "
            "WHEN NEW.load_id = 2 BEGIN SELECT RAISE(ABORT, 'simulated failure'); END;"
        )
    _source(monkeypatch, {period: _package(period, "revision-2") for period in periods}, rows)
    with pytest.raises(sqlite3.IntegrityError, match="simulated failure"):
        refresh_cnmc_market.refresh(database)
    assert _loads(database) == [(period, "revision-1", 1) for period in periods]


def test_refresh_never_rewrites_unchanged_quarters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "mapa.sqlite"
    rows = {"resource-2024T4": [_row("2024T4", 1)], "resource-2025T1": [_row("2025T1", 1)]}
    packages = {"2024T4": _package("2024T4"), "2025T1": _package("2025T1")}
    _source(monkeypatch, packages, rows)
    refresh_cnmc_market.refresh(database)
    with sqlite3.connect(database) as connection:
        for table in market_store.MARKET_TABLES[1:]:
            connection.executescript(
                f"CREATE TRIGGER preserve_{table} BEFORE DELETE ON {table} "
                "WHEN OLD.load_id = 2 BEGIN SELECT RAISE(ABORT, 'unchanged quarter rewritten'); END;"
            )
    _source(monkeypatch, {**packages, "2024T4": _package("2024T4", "revision-2")}, rows)
    assert refresh_cnmc_market.refresh(database) == [("2024T4", 1)]

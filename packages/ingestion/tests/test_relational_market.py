"""Relational dimensions retain source identity and historical observations."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from electricity_map_ingestion import market_store

from scripts.normalize_database import migrate


def _load(period: str, license_code: str = "CC-BY-SA-4.0") -> tuple:
    return (
        "electricity",
        period,
        f"package-{period}",
        f"resource-{period}",
        "revision",
        2,
        "now",
        "source",
        license_code,
        f"https://license/{license_code}",
        "conditions",
        "attribution",
    )


def _rows(period: str, name: str | None) -> list[tuple]:
    return [
        ("electricity", period, source_id, "R1-001", "Red", "R2-001", name, "marketer", "2.0TD", "13", 10, -20)
        for source_id in (1, 2)
    ]


def test_dimensions_are_shared_but_history_and_repeated_source_rows_survive() -> None:
    with closing(sqlite3.connect(":memory:")) as connection:
        market_store.initialize(connection)
        with connection:
            market_store.write_quarter(connection, _load("2024T4"), _rows("2024T4", "Old name"))
            market_store.write_quarter(connection, _load("2025T1"), _rows("2025T1", "New name"))
        assert connection.execute("SELECT COUNT(*) FROM licenses").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM sources").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM companies").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM company_names").fetchone() == (3,)
        assert connection.execute("SELECT COUNT(*) FROM market_rows").fetchone() == (4,)
        assert connection.execute(
            "SELECT period, marketer_name, SUM(supplies) FROM market_rows_view GROUP BY period ORDER BY period"
        ).fetchall() == [("2024T4", "Old name", 20), ("2025T1", "New name", 20)]
        with connection:
            market_store.write_quarter(connection, _load("2025T2", "another-license"), _rows("2025T2", None))
        assert connection.execute("SELECT COUNT(*) FROM licenses").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM sources").fetchone() == (2,)
        assert connection.execute("SELECT license_id FROM loads_view WHERE period='2024T4'").fetchone() == (
            "CC-BY-SA-4.0",
        )
        assert connection.execute(
            "SELECT DISTINCT marketer_code, marketer_name FROM market_rows_view WHERE period='2025T2'"
        ).fetchone() == ("R2-001", None)
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute("UPDATE market_rows SET load_id=999 WHERE load_id=1")


def test_staged_dimension_ids_are_remapped_to_the_live_database(tmp_path: Path) -> None:
    live = tmp_path / "live.sqlite"
    stage = tmp_path / "stage.sqlite"
    with closing(sqlite3.connect(live)) as connection:
        market_store.initialize(connection)
        with connection:
            market_store.write_quarter(connection, _load("2024T4"), _rows("2024T4", "Original"))
    with closing(sqlite3.connect(stage)) as connection:
        market_store.initialize(connection)
        with connection:
            market_store.write_quarter(connection, _load("2025T1"), _rows("2025T1", "Revised name"))
    market_store.publish(live, stage, market_store.current_revisions(live), {"2025T1": _load("2025T1")[2:6]})
    with closing(sqlite3.connect(live)) as connection:
        assert connection.execute(
            "SELECT DISTINCT period, marketer_name FROM market_rows_view ORDER BY period"
        ).fetchall() == [("2024T4", "Original"), ("2025T1", "Revised name")]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_migration_keeps_every_value_and_unrelated_tables(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.sqlite"
    legacy = tmp_path / "legacy.sqlite"
    destination = tmp_path / "normalized.sqlite"
    with closing(sqlite3.connect(fixture)) as connection:
        market_store.initialize(connection)
        with connection:
            market_store.write_quarter(
                connection,
                _load("2024T4"),
                _rows("2024T4", "Observed name"),
                [("electricity", "2024T4", "marketer", "R2-001", "Observed name", 1)],
                [("electricity", "2024T4", 1, "negative_energy", "-20")],
            )
    with closing(sqlite3.connect(legacy)) as connection:
        connection.execute("ATTACH DATABASE ? AS fixture", (str(fixture),))
        for table in ("loads", "market_rows", "company_names", "ingestion_issues"):
            connection.execute(f"CREATE TABLE {table} AS SELECT * FROM fixture.{table}_view")
        connection.executescript("CREATE TABLE coverage (value TEXT); INSERT INTO coverage VALUES ('preserved');")
    original = legacy.read_bytes()
    migrate(legacy, destination)
    assert legacy.read_bytes() == original
    with closing(sqlite3.connect(destination)) as connection:
        assert connection.execute("SELECT * FROM coverage").fetchone() == ("preserved",)
        assert connection.execute("SELECT COUNT(*) FROM market_rows").fetchone() == (2,)
        assert connection.execute("SELECT extinct_mark FROM load_company_names").fetchone() == (1,)
        assert connection.execute("SELECT detail FROM ingestion_issues").fetchone() == ("-20",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

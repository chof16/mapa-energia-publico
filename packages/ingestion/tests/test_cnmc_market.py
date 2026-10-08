"""Checks for source anomalies that must not distort the historical series."""

from __future__ import annotations

import sqlite3

import pytest
from electricity_map_ingestion.cnmc_market import import_quarter
from electricity_map_ingestion.market_store import initialize


def _package(modified: str = "2026-09-16T00:00:00") -> dict:
    return {
        "title": "Mercado minorista de electricidad 2024T4",
        "name": "ds_test",
        "license_id": "CC-BY-SA-4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "metadata_modified": modified,
        "extras": [{"key": "periodo", "value": "2024T4"}],
        "resources": [{"position": 0, "datastore_active": True, "id": "resource-test"}],
    }


def _row(source_id: int, **changes: object) -> dict:
    row = {
        "_id": source_id,
        "fecha": "2024T4",
        "anno_envio": "2024",
        "trimestre_envio": "T4",
        "cod_dis": "R1-001",
        "descripcion_distribuidor": "Red, S.A.",
        "cod_com": "R2-004",
        "descripcion_comercializador": "Consumidor Directo",
        "tarifa_acceso": "2.0TD",
        "ccaa": "Madrid, Comunidad de",
        "numero_suministro": 2.0,
        "energia": -294.0,
    }
    row.update(changes)
    return row


@pytest.fixture
def database() -> sqlite3.Connection:
    with sqlite3.connect(":memory:") as connection:
        initialize(connection)
        yield connection


def test_preserves_repeated_rows_and_classifies_codes(database: sqlite3.Connection) -> None:
    rows = [
        _row(1),
        _row(2),  # Same business key and values; source ID is distinct.
        _row(3, cod_com="Consumidor Directo", numero_suministro=3, energia=0),
        _row(4, cod_com="No Disponible", descripcion_comercializador="No Disponible", energia=0),
    ]
    assert import_quarter(database, _package(), iter(rows)) == ("2024T4", 4, True)
    assert database.execute("SELECT COUNT(*), SUM(supplies) FROM market_rows_view").fetchone() == (4, 9)
    assert database.execute(
        "SELECT category, COUNT(*) FROM market_rows_view GROUP BY category ORDER BY category"
    ).fetchall() == [("direct_consumer", 1), ("marketer", 2), ("unavailable", 1)]
    assert database.execute("SELECT marketer_code FROM market_rows_view WHERE source_id=1").fetchone() == ("R2-004",)
    assert database.execute("SELECT SUM(energy_kwh) FROM market_rows").fetchone() == (-588,)
    kinds = {row[0] for row in database.execute("SELECT kind FROM ingestion_issues")}
    assert kinds == {"marketer_code_direct_description", "repeated_identical_key", "negative_energy"}


def test_bad_revision_does_not_replace_previous_quarter(database: sqlite3.Connection) -> None:
    import_quarter(database, _package(), iter([_row(1)]))
    with pytest.raises(ValueError, match="Unknown community"):
        import_quarter(database, _package("newer"), iter([_row(2, ccaa="Unknown")]))
    assert database.execute("SELECT source_id FROM market_rows_view").fetchall() == [(1,)]
    assert database.execute("SELECT metadata_modified FROM loads").fetchone() == ("2026-09-16T00:00:00",)


def test_unchanged_metadata_skips_and_new_revision_replaces(database: sqlite3.Connection) -> None:
    import_quarter(database, _package(), iter([_row(1)]))
    assert import_quarter(database, _package(), iter(())) == ("2024T4", 0, False)
    assert import_quarter(database, _package("newer"), iter([_row(2)])) == ("2024T4", 1, True)
    assert database.execute("SELECT source_id FROM market_rows_view").fetchall() == [(2,)]

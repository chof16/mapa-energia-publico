"""Relational persistence for market quarters; schema installation is explicit."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import closing
from importlib.resources import files
from pathlib import Path

MARKET_TABLES = ("loads", "market_rows", "load_company_names", "ingestion_issues")
MARKET_SECTOR = "electricity"
type Revisions = dict[str, tuple[str, str, str]]
type ExpectedLoads = dict[str, tuple[str, str, str, int]]


def initialize(connection: sqlite3.Connection) -> None:
    """Install the versioned schema on a new database, or verify an existing one."""
    connection.execute("PRAGMA foreign_keys=ON")
    if connection.execute("SELECT 1 FROM sqlite_master WHERE name='loads'").fetchone():
        validate_schema(connection)
        return
    script = files("electricity_map_ingestion").joinpath("sql/market_v2.sql").read_text()
    for statement in script.split(";"):
        if statement.strip():
            connection.execute(statement)
    connection.commit()


def validate_schema(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone() is None:
        raise ValueError("Market schema requires migration to version 2")
    if connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone() != (2,):
        raise ValueError("Unsupported market schema version")


class _Dimensions:
    """Intern dimensions once per distinct value, not once per market row."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.cache: dict[tuple, int] = {}

    def get(self, table: str, columns: tuple[str, ...], values: tuple) -> int:
        key = (table, values)
        if key not in self.cache:
            where = " AND ".join(f"{column} IS ?" for column in columns)
            row = self.connection.execute(f"SELECT id FROM {table} WHERE {where}", values).fetchone()
            if row is None:
                placeholders = ",".join("?" for _ in columns)
                cursor = self.connection.execute(
                    f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values
                )
                row = (cursor.lastrowid,)
            self.cache[key] = row[0]
        return self.cache[key]

    def name(self, sector_id: int, role: str, code: str, name: str | None) -> int:
        company = self.get("companies", ("sector_id", "role", "code"), (sector_id, role, code))
        return self.get("company_names", ("company_id", "name"), (company, name))


def write_quarter(
    connection: sqlite3.Connection,
    load: tuple,
    rows: Iterable[tuple],
    names: Iterable[tuple] = (),
    issues: Iterable[tuple] = (),
) -> int:
    """Replace one quarter inside the caller's transaction, translating dimension IDs."""
    (
        sector,
        period,
        package,
        resource,
        modified,
        count,
        loaded,
        url,
        license_code,
        license_url,
        conditions,
        attribution,
    ) = load
    dimensions = _Dimensions(connection)
    sector_id = dimensions.get("sectors", ("code",), (sector,))
    period_id = dimensions.get("periods", ("year", "quarter"), (int(period[:4]), int(period[-1])))
    license_id = dimensions.get("licenses", ("code", "url"), (license_code, license_url))
    source_id = dimensions.get(
        "sources", ("url", "license_id", "conditions_url", "attribution"), (url, license_id, conditions, attribution)
    )
    existing = connection.execute(
        "SELECT id FROM loads WHERE sector_id=? AND period_id=?", (sector_id, period_id)
    ).fetchone()
    if existing:
        load_id = existing[0]
        for table in reversed(MARKET_TABLES[1:]):
            connection.execute(f"DELETE FROM {table} WHERE load_id=?", (load_id,))
        connection.execute(
            """UPDATE loads SET source_id=?, package_name=?, resource_id=?, metadata_modified=?,
               row_count=?, loaded_at=? WHERE id=?""",
            (source_id, package, resource, modified, count, loaded, load_id),
        )
    else:
        load_id = connection.execute(
            """INSERT INTO loads (sector_id, period_id, source_id, package_name, resource_id,
               metadata_modified, row_count, loaded_at) VALUES (?,?,?,?,?,?,?,?)""",
            (sector_id, period_id, source_id, package, resource, modified, count, loaded),
        ).lastrowid
    normalized = []
    communities = set()
    for row in rows:
        if row[:2] != (sector, period):
            raise ValueError("Market row belongs to another load")
        (
            _,
            _,
            row_id,
            distributor,
            distributor_name,
            marketer,
            marketer_name,
            category,
            tariff,
            community,
            supplies,
            energy,
        ) = row
        distributor_name_id = dimensions.name(sector_id, "distributor", distributor, distributor_name)
        marketer_name_id = dimensions.name(sector_id, "marketer", marketer, marketer_name) if marketer else None
        tariff_id = dimensions.get("tariffs", ("code",), (tariff,))
        communities.add((community,))
        normalized.append(
            (load_id, row_id, distributor_name_id, marketer_name_id, category, tariff_id, community, supplies, energy)
        )
    connection.executemany("INSERT OR IGNORE INTO communities VALUES (?)", communities)
    connection.executemany("INSERT INTO market_rows VALUES (?,?,?,?,?,?,?,?,?)", normalized)
    connection.executemany(
        "INSERT INTO load_company_names VALUES (?,?,?)",
        ((load_id, dimensions.name(sector_id, role, code, name), extinct) for _, _, role, code, name, extinct in names),
    )
    connection.executemany(
        "INSERT INTO ingestion_issues VALUES (?,?,?,?)",
        ((load_id, row_id, kind, detail) for _, _, row_id, kind, detail in issues),
    )
    return load_id


def revisions(connection: sqlite3.Connection) -> Revisions:
    return {
        period: (name, resource, modified)
        for period, name, resource, modified in connection.execute(
            "SELECT period, package_name, resource_id, metadata_modified FROM loads_view WHERE sector=?",
            (MARKET_SECTOR,),
        )
    }


def current_revisions(database: Path) -> Revisions:
    if not database.exists():
        return {}
    if not database.is_file():
        raise ValueError("Live database must be a regular SQLite file")
    with closing(sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)) as connection:
        validate_schema(connection)
        return revisions(connection)


def validate_staged(
    connection: sqlite3.Connection,
    expected_loads: ExpectedLoads,
    *,
    source_url: str,
    conditions_url: str,
    attribution: str,
) -> None:
    validate_schema(connection)
    if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise ValueError("Staged SQLite integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("Staged SQLite foreign key check failed")
    mismatch = connection.execute(
        """SELECT l.id FROM loads l LEFT JOIN market_rows r ON r.load_id=l.id
           GROUP BY l.id HAVING l.row_count < 1 OR l.row_count != COUNT(r.source_row_id) LIMIT 1"""
    ).fetchone()
    if mismatch:
        raise ValueError(f"Staged load count mismatch for {mismatch}")
    for period, expected in expected_loads.items():
        actual = connection.execute(
            """SELECT package_name, resource_id, metadata_modified, row_count FROM loads_view
               WHERE sector=? AND period=? AND source_url=? AND license_id='CC-BY-SA-4.0'
               AND TRIM(license_url) != '' AND conditions_url=? AND attribution=?""",
            (MARKET_SECTOR, period, source_url, conditions_url, attribution),
        ).fetchone()
        if actual != expected:
            raise ValueError(f"Staged source metadata/count mismatch for {period}")


def publish(database: Path, stage: Path, previous: Revisions, expected_loads: ExpectedLoads) -> None:
    """Commit changed quarters together, remapping stage-local foreign keys."""
    with (
        closing(sqlite3.connect(database, timeout=30)) as live,
        closing(sqlite3.connect(f"{stage.resolve().as_uri()}?mode=ro", uri=True)) as incoming,
    ):
        initialize(live)
        if live.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
            raise ValueError("Live database must support SQLite WAL mode")
        try:
            live.execute("BEGIN IMMEDIATE")
            if revisions(live) != previous:
                raise ValueError("Live market loads changed during refresh")
            for period, expected in expected_loads.items():
                parameters = (MARKET_SECTOR, period)
                load = incoming.execute("SELECT * FROM loads_view WHERE sector=? AND period=?", parameters).fetchone()
                load_id = write_quarter(
                    live,
                    load,
                    incoming.execute("SELECT * FROM market_rows_view WHERE sector=? AND period=?", parameters),
                    incoming.execute("SELECT * FROM company_names_view WHERE sector=? AND period=?", parameters),
                    incoming.execute("SELECT * FROM ingestion_issues_view WHERE sector=? AND period=?", parameters),
                )
                count = live.execute("SELECT COUNT(*) FROM market_rows WHERE load_id=?", (load_id,)).fetchone()[0]
                if count != expected[3]:
                    raise ValueError(f"Published load mismatch for {period}")
            if live.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("Published foreign key check failed")
            live.commit()
        except Exception:
            live.rollback()
            raise

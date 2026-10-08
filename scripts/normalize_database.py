"""Migrate a legacy SQLite snapshot to a separate, verified relational database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from electricity_map_ingestion.market_store import initialize, write_quarter

from scripts.export_database import _inspect

LEGACY_TABLES = ("loads", "market_rows", "company_names", "ingestion_issues")


def _digest(connection: sqlite3.Connection, relation: str, sector: str, period: str) -> str:
    digest = hashlib.sha256()
    columns = len(connection.execute(f"PRAGMA table_info({relation})").fetchall())
    order = ",".join(str(index) for index in range(1, columns + 1))
    for row in connection.execute(
        f"SELECT * FROM {relation} WHERE sector=? AND period=? ORDER BY {order}", (sector, period)
    ):
        digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def migrate(source: Path, destination: Path) -> dict:
    """Keep the original file and publish only after every legacy value matches."""
    if source.resolve() == destination.resolve() or destination.exists():
        raise ValueError("Migration destination must be a new file, different from the source")
    _inspect(source, "market")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".normalize-", dir=destination.parent) as work:
        snapshot = Path(work) / "snapshot.sqlite"
        output = Path(work) / "normalized.sqlite"
        with (
            closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)) as original,
            closing(sqlite3.connect(snapshot)) as legacy,
        ):
            original.backup(legacy)
        with closing(sqlite3.connect(snapshot)) as legacy, closing(sqlite3.connect(output)) as normalized:
            # Preserve all non-market tables, indexes and decisions exactly.
            legacy.backup(normalized)
            normalized.execute("PRAGMA foreign_keys=OFF")
            for table in reversed(LEGACY_TABLES):
                normalized.execute(f"DROP TABLE {table}")
            initialize(normalized)
            with normalized:
                for load in legacy.execute("SELECT * FROM loads ORDER BY sector, period"):
                    sector, period = load[:2]
                    parameters = (sector, period)
                    write_quarter(
                        normalized,
                        load,
                        legacy.execute("SELECT * FROM market_rows WHERE sector=? AND period=?", parameters),
                        legacy.execute("SELECT * FROM company_names WHERE sector=? AND period=?", parameters),
                        legacy.execute("SELECT * FROM ingestion_issues WHERE sector=? AND period=?", parameters),
                    )
                    for table in LEGACY_TABLES:
                        if _digest(legacy, table, sector, period) != _digest(
                            normalized, f"{table}_view", sector, period
                        ):
                            raise ValueError(f"Migration changed {table} values for {sector}/{period}")
            if normalized.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("Migration has broken foreign keys")
            normalized.execute("VACUUM")
            normalized.execute("PRAGMA journal_mode=DELETE")
        details = _inspect(output, "market")
        os.link(output, destination)
    return {"database": str(destination), "bytes": destination.stat().st_size, **details}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("datos/mapa.sqlite"))
    parser.add_argument("--database", type=Path, default=Path("datos/mapa-v2.sqlite"))
    args = parser.parse_args()
    print(json.dumps(migrate(args.source, args.database), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

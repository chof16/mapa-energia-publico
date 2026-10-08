"""Initialize one SQLite database from market data and reviewed coverage."""

from __future__ import annotations

import argparse
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from electricity_map_api.distribution.store import build_database

from scripts.export_database import _inspect
from scripts.normalize_database import migrate


def build(market: Path, destination: Path) -> dict[str, object]:
    """Initialize once; use the dedicated refresh commands for subsequent changes."""
    if market.resolve() == destination.resolve():
        raise ValueError("Market source and combined database must differ")
    if destination.exists():
        raise ValueError("Combined database already exists; use refresh-cnmc-market or build-distribution-database")
    _inspect(market, "market")
    destination.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".sqlite", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(f"{market.resolve().as_uri()}?mode=ro", uri=True)) as source:
            normalized = source.execute("SELECT 1 FROM sqlite_master WHERE name='loads_view'").fetchone()
            if normalized:
                with closing(sqlite3.connect(temporary)) as combined:
                    source.backup(combined)
        if not normalized:
            temporary.unlink()
            migrate(market, temporary)
        build_database(temporary)
        details = _inspect(temporary, "combined")
        # A hard link publishes the completed file without overwriting a raced creator.
        os.link(temporary, destination)
        with closing(sqlite3.connect(destination)) as combined:
            if combined.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                raise ValueError("Combined database must support WAL mode")
        details["journal_mode"] = "wal"
        return details
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", type=Path, default=Path("datos/mercado.sqlite"))
    parser.add_argument("--database", type=Path, default=Path("datos/mapa-v2.sqlite"))
    args = parser.parse_args()
    print(build(args.market, args.database))


if __name__ == "__main__":
    main()

"""Stage changed CNMC electricity quarters, then publish the validated batch."""

from __future__ import annotations

import argparse
import fcntl
import os
import sqlite3
import tempfile
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from electricity_map_ingestion import cnmc_client, cnmc_electricity, electricity_store


def refresh(database: Path, periods: Sequence[str] | None = None) -> list[tuple[str, int]]:
    """Return updated quarters; preserve every unrelated table and live inode."""
    database = database.resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    lock_path = database.with_name(f"{database.name}.refresh.lock")
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        packages = cnmc_electricity.discover()
        if not packages:
            raise ValueError("CNMC catalog has no published electricity quarters")
        selected = list(dict.fromkeys(periods)) if periods else list(packages)
        unknown = set(selected) - packages.keys()
        if unknown:
            raise ValueError(f"Unknown or unpublished quarters: {', '.join(sorted(unknown))}")

        previous = electricity_store.current_revisions(database)
        changed = [
            period
            for period in selected
            if previous.get(period) != cnmc_electricity.package_metadata(packages[period])[1:]
        ]
        if not changed:
            return []

        descriptor, stage_name = tempfile.mkstemp(prefix=f".{database.name}.", suffix=".staging", dir=database.parent)
        os.close(descriptor)
        stage = Path(stage_name)
        published = []
        expected_loads = {}
        try:
            with closing(sqlite3.connect(stage)) as staged:
                electricity_store.initialize(staged)
                for period in changed:
                    package = packages[period]
                    package_name, resource_id, modified = cnmc_electricity.package_metadata(package)[1:]
                    _, count, _ = cnmc_electricity.import_quarter(
                        staged, package, cnmc_client.online_rows(resource_id), force=True
                    )
                    expected_loads[period] = (package_name, resource_id, modified, count)
                    published.append((period, count))
                electricity_store.validate_staged(
                    staged,
                    expected_loads,
                    source_url=cnmc_electricity.SOURCE_URL,
                    conditions_url=cnmc_client.CONDITIONS_URL,
                    attribution=cnmc_client.ATTRIBUTION,
                )
            current = cnmc_electricity.discover()
            for period in changed:
                if period not in current or (
                    cnmc_electricity.package_metadata(current[period])
                    != cnmc_electricity.package_metadata(packages[period])
                ):
                    raise ValueError(f"Source metadata changed during refresh for {period}")
            electricity_store.publish(database, stage, previous, expected_loads)
            return published
        finally:
            stage.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Live SQLite file used by the API")
    parser.add_argument("--period", action="append", help="Only refresh this quarter; repeat for several")
    args = parser.parse_args()
    published = refresh(args.database, args.period)
    if published:
        for period, count in published:
            print(f"{period}: published {count} rows")
    else:
        print("CNMC catalog unchanged; market tables not updated")


if __name__ == "__main__":
    main()

"""Build the reviewed distribution database from the versioned decision manifest."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from importlib.resources import files
from pathlib import Path

from electricity_map_api.distribution.schemas import CoverageEvidence

DISTRIBUTION_TABLES = ("snapshot", "distributor_identity", "group_association", "claim_decision")


def _initialize(connection: sqlite3.Connection) -> None:
    """Install distribution tables in a new database or an empty staging file."""
    schema = files("electricity_map_api.distribution").joinpath("sql/distribution_v1.sql").read_text(encoding="utf-8")
    # executescript commits an open transaction; execute DDL individually.
    for statement in schema.split(";"):
        if statement.strip():
            connection.execute(statement)


def _publish_tables(destination: Path, staged: Path) -> None:
    """Replace only reviewed coverage tables, preserving market data and inode."""
    with closing(sqlite3.connect(destination, timeout=30)) as live:
        live.execute("PRAGMA foreign_keys=ON")
        live.execute("ATTACH DATABASE ? AS incoming", (str(staged),))
        try:
            live.execute("BEGIN IMMEDIATE")
            existing = [live.execute(f"PRAGMA main.table_info({table})").fetchall() for table in DISTRIBUTION_TABLES]
            if not any(existing):
                _initialize(live)
            elif not all(existing):
                raise ValueError("Incomplete distribution schema in live database")
            for table in DISTRIBUTION_TABLES:
                if (
                    live.execute(f"PRAGMA main.table_info({table})").fetchall()
                    != live.execute(f"PRAGMA incoming.table_info({table})").fetchall()
                ):
                    raise ValueError(f"Unexpected distribution schema for {table}")
            changed = [
                table
                for table in DISTRIBUTION_TABLES
                if any(
                    live.execute(
                        f"SELECT * FROM {left}.{table} EXCEPT SELECT * FROM {right}.{table} LIMIT 1"
                    ).fetchone()
                    is not None
                    for left, right in (("main", "incoming"), ("incoming", "main"))
                )
            ]
            # An unchanged child can still refer to a parent being replaced.
            live.execute("PRAGMA defer_foreign_keys=ON")
            for table in reversed(changed):
                live.execute(f"DELETE FROM main.{table}")
            for table in changed:
                live.execute(f"INSERT INTO main.{table} SELECT * FROM incoming.{table}")
            if live.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("Distribution foreign key check failed")
            live.commit()
        except Exception:
            live.rollback()
            raise
        finally:
            live.execute("DETACH DATABASE incoming")


def load_manifest() -> dict:
    """Read the reviewed source file shipped with the API package."""
    return json.loads(files("electricity_map_api.distribution").joinpath("claims.json").read_text(encoding="utf-8"))


def build_database(destination: Path, manifest: dict | None = None) -> None:
    """Validate decisions, then transactionally update changed coverage tables."""
    source = load_manifest() if manifest is None else manifest
    if source["complete"] is not False:
        raise ValueError("Provincial coverage must remain incomplete")
    distributor_codes = {row["code"] for row in source["distributors"]}
    if len(distributor_codes) != len(source["distributors"]):
        raise ValueError("Duplicate distributor identity")
    claim_ids: set[str] = set()
    for claim in source["claims"]:
        if claim["id"] in claim_ids:
            raise ValueError(f"Duplicate claim ID: {claim['id']}")
        claim_ids.add(claim["id"])
        if claim["distributor_code"] not in distributor_codes:
            raise ValueError(f"Unknown distributor: {claim['distributor_code']}")
        if not claim["decision_reason"].strip() or not claim["review_source_url"].startswith("https://"):
            raise ValueError(f"Missing decision reason or source: {claim['id']}")
        if claim["status"] == "accepted":
            evidence = CoverageEvidence.model_validate(claim["evidence"])
            if evidence.source_url != claim["review_source_url"]:
                raise ValueError(f"Evidence source differs from review source: {claim['id']}")
        elif claim["status"] not in {"rejected", "superseded"}:
            raise ValueError(f"Invalid status: {claim['id']}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as connection, connection:
            connection.execute("PRAGMA foreign_keys=ON")
            _initialize(connection)
            connection.execute("INSERT INTO snapshot VALUES (1, ?, 0)", (source["snapshot_date"],))
            connection.executemany(
                "INSERT INTO distributor_identity VALUES (:code, :name, :registry_source_url)",
                source["distributors"],
            )
            connection.executemany(
                "INSERT INTO group_association VALUES (?, ?, ?)",
                [
                    (row["distributor_code"], row["group_name"], json.dumps(row["evidence"], ensure_ascii=False))
                    for row in source["group_associations"]
                ],
            )
            connection.executemany(
                "INSERT INTO claim_decision VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        row["id"],
                        row["province_code"],
                        row["distributor_code"],
                        row["status"],
                        row["decision_reason"],
                        row["review_source_url"],
                        row["checked_on"],
                        json.dumps(row["evidence"], ensure_ascii=False) if row["evidence"] else None,
                    )
                    for row in source["claims"]
                ],
            )
        if destination.exists():
            _publish_tables(destination, temporary)
        else:
            os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Create or replace the configured distribution snapshot."""
    import argparse

    parser = argparse.ArgumentParser(description="Build the reviewed distribution SQLite snapshot")
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    build_database(args.database)

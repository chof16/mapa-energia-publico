"""Create a verified local SQLite backup and portable SQL export."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

SQLITE_MAGIC = b"SQLite format 3\x00"
MAX_UPLOAD_BYTES = 20 * 1024**3
REQUIRED_TABLES = {
    "market": ("market_rows", "loads"),
    "distribution": ("claim_decision", "snapshot"),
    "combined": ("market_rows", "loads", "claim_decision", "snapshot"),
}


def _inspect(path: Path, kind: str) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError(f"Missing or oversized {kind} database: {path}")
    with path.open("rb") as stream:
        if stream.read(len(SQLITE_MAGIC)) != SQLITE_MAGIC:
            raise ValueError(f"Invalid SQLite header: {path}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError(f"SQLite integrity check failed: {path}")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError(f"SQLite foreign key check failed: {path}")
        details: dict[str, object] = {}
        for table in REQUIRED_TABLES[kind]:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count < 1:
                raise ValueError(f"Empty required table {table} in {path}")
            details[table] = count
        if kind in {"distribution", "combined"}:
            details["decisions"] = dict(
                connection.execute("SELECT status, COUNT(*) FROM claim_decision GROUP BY status").fetchall()
            )
            details["documented_provinces"] = connection.execute(
                "SELECT COUNT(DISTINCT province_code) FROM claim_decision WHERE status = 'accepted'"
            ).fetchone()[0]
            details["snapshot"] = connection.execute(
                "SELECT snapshot_date, complete FROM snapshot WHERE id = 1"
            ).fetchone()
            if details["snapshot"] is None or details["snapshot"][1] != 0:
                raise ValueError("Distribution snapshot must remain incomplete")
        if kind in {"market", "combined"}:
            normalized = connection.execute("SELECT 1 FROM sqlite_master WHERE name='loads_view'").fetchone()
            relation = "loads_view" if normalized else "loads"
            details["periods"] = connection.execute(f"SELECT COUNT(DISTINCT period) FROM {relation}").fetchone()[0]
            if normalized:
                details["table_counts"] = {
                    table: connection.execute(f"SELECT COUNT(*) FROM {_identifier(table)}").fetchone()[0]
                    for (table,) in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    ).fetchall()
                }
        details["journal_mode"] = connection.execute("PRAGMA journal_mode").fetchone()[0]
        details["page_size"] = connection.execute("PRAGMA page_size").fetchone()[0]
        details["auto_vacuum"] = connection.execute("PRAGMA auto_vacuum").fetchone()[0]
        details["encoding"] = connection.execute("PRAGMA encoding").fetchone()[0]
        return details
    finally:
        connection.close()


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _ordered_dump(connection: sqlite3.Connection):
    """Export parent tables before children, so every upload batch satisfies FKs."""
    tables = dict(
        connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    )
    dependencies = {
        name: {row[2] for row in connection.execute(f"PRAGMA foreign_key_list({_identifier(name)})")} for name in tables
    }
    ordered = []
    while dependencies:
        ready = sorted(name for name, parents in dependencies.items() if not parents.intersection(dependencies))
        if not ready:
            raise ValueError("Cannot export a cyclic foreign key graph in separate batches")
        for name in ready:
            ordered.append(name)
            del dependencies[name]
    yield "BEGIN TRANSACTION;"
    for table in ordered:
        yield tables[table] + ";"
        for row in connection.execute(f"SELECT * FROM {_identifier(table)}"):
            values = []
            for value in row:
                if value is None:
                    values.append("NULL")
                elif isinstance(value, int):
                    values.append(str(value))
                elif isinstance(value, str) and "\x00" not in value:
                    values.append("'" + value.replace("'", "''") + "'")
                else:
                    raise ValueError(f"Unsupported SQL export value in {table}")
            yield f"INSERT INTO {_identifier(table)} VALUES({','.join(values)});"
    for (statement,) in connection.execute(
        "SELECT sql FROM sqlite_master WHERE type IN ('index', 'view', 'trigger') "
        "AND sql IS NOT NULL ORDER BY type, name"
    ):
        yield statement + ";"
    yield "COMMIT;"


def prepare(source: Path, destination: Path, kind: str) -> dict[str, object]:
    """Back up a consistent source snapshot and publish a checked WAL-mode copy."""
    if source.resolve() == destination.resolve():
        raise ValueError("Source and upload destination must differ")
    source_details = _inspect(source, kind)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".sqlite", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        source_connection = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
        try:
            with closing(sqlite3.connect(temporary)) as copy:
                source_connection.backup(copy)
                if copy.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                    raise ValueError(f"Cannot enable WAL mode: {destination}")
                copy.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            source_connection.close()
        if any(Path(f"{temporary}{suffix}").exists() for suffix in ("-wal", "-shm")):
            raise ValueError(f"Upload file has uncheckpointed sidecars: {temporary}")
        upload_details = _inspect(temporary, kind)
        if {key: value for key, value in source_details.items() if key != "journal_mode"} != {
            key: value for key, value in upload_details.items() if key != "journal_mode"
        } or upload_details["journal_mode"] != "wal":
            raise ValueError(f"Upload copy does not match its source: {source}")
        if (upload_details["page_size"], upload_details["auto_vacuum"], upload_details["encoding"]) != (
            4096,
            0,
            "UTF-8",
        ):
            raise ValueError(f"Upload copy has unsupported SQLite settings: {destination}")
        _finalize_sqlite_upload(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm"):
            Path(f"{temporary}{suffix}").unlink(missing_ok=True)
    return {
        "file": str(destination),
        "bytes": destination.stat().st_size,
        "sha256": _hash(destination),
        **upload_details,
    }


def prepare_sql_dump(source: Path, destination: Path, kind: str) -> dict[str, object]:
    """Export portable SQL and verify local replay with foreign keys enabled."""
    if source.resolve() == destination.resolve():
        raise ValueError("Source and SQL destination must differ")
    source_details = _inspect(source, kind)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".sql", dir=destination.parent)
    temporary = Path(temporary_name)
    statement_count = 0
    try:
        with (
            closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)) as connection,
            os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream,
        ):
            batch_prefix = ""
            batch_values: list[str] = []
            batch_bytes = 0

            def flush_batch() -> None:
                nonlocal batch_prefix, batch_bytes, statement_count
                if batch_values:
                    stream.write(f"{batch_prefix} VALUES{','.join(batch_values)};\n")
                    statement_count += 1
                    batch_prefix = ""
                    batch_values.clear()
                    batch_bytes = 0

            for statement in _ordered_dump(connection):
                prefix, separator, values = statement.partition(" VALUES")
                if statement.startswith('INSERT INTO "') and separator and values.endswith(";"):
                    if prefix != batch_prefix or len(batch_values) >= 250 or batch_bytes + len(values) > 128_000:
                        flush_batch()
                    batch_prefix = prefix
                    batch_values.append(values[:-1])
                    batch_bytes += len(values)
                    continue
                flush_batch()
                stream.write(statement)
                stream.write("\n")
                statement_count += 1
            flush_batch()
            stream.flush()
            os.fsync(stream.fileno())

        with tempfile.TemporaryDirectory(prefix=".sql-replay-", dir=destination.parent) as replay_dir:
            replay = Path(replay_dir) / "replay.sqlite"
            with closing(sqlite3.connect(replay)) as connection, temporary.open(encoding="utf-8") as stream:
                connection.execute("PRAGMA foreign_keys=ON")
                pending = ""
                for line in stream:
                    pending += line
                    if sqlite3.complete_statement(pending):
                        connection.execute(pending)
                        pending = ""
                if pending.strip():
                    raise ValueError(f"Incomplete SQL export: {destination}")
            replay_details = _inspect(replay, kind)
            if {key: value for key, value in source_details.items() if key != "journal_mode"} != {
                key: value for key, value in replay_details.items() if key != "journal_mode"
            }:
                raise ValueError(f"SQL replay does not match SQLite source: {source}")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "file": str(destination),
        "bytes": destination.stat().st_size,
        "sha256": _hash(destination),
        "statements": statement_count,
    }


def _finalize_sqlite_upload(path: Path) -> None:
    # Read-only validation of a WAL database may create empty -wal/-shm files.
    # A final writable close checkpoints and removes them without changing rows.
    with closing(sqlite3.connect(path)) as connection:
        if connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
            raise ValueError(f"SQLite WAL checkpoint failed: {path}")
    if any(Path(f"{path}{suffix}").exists() for suffix in ("-wal", "-shm")):
        raise ValueError(f"Upload file has SQLite sidecars: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("datos/mapa-v2.sqlite"))
    parser.add_argument("--output-dir", type=Path, default=Path("datos/exports"))
    args = parser.parse_args()
    upload = args.output_dir / "mapa.sqlite"
    sqlite_result = prepare(args.database, upload, "combined")
    sql_result = prepare_sql_dump(upload, upload.with_suffix(".sql"), "combined")
    _finalize_sqlite_upload(upload)
    print(json.dumps({"sqlite": sqlite_result, "sql": sql_result}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

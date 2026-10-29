"""Prepare separate, additive PostgreSQL artifacts; never connect to a remote database."""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from electricity_map_ingestion.gas_retail import MAX_BYTES, Evidence
from electricity_map_ingestion.gas_retail_store import TABLES, revision_id, schema_sql, verify_load


def literal(value: str | int | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    if "\x00" in value:
        raise ValueError("PostgreSQL text cannot contain NUL")
    return "'" + value.replace("'", "''") + "'"


def copy_field(value: str | int | None) -> str:
    """Encode COPY text without confusing NULL, delimiters or psql's end marker."""
    if value is None:
        return r"\N"
    text = str(value)
    if "\x00" in text:
        raise ValueError("PostgreSQL text cannot contain NUL")
    return text.translate(str.maketrans({"\\": r"\\", "\t": r"\t", "\n": r"\n", "\r": r"\r"}))


def export(database: Path, load_id: str, output: Path | None = None) -> dict[str, int]:
    if not 16 <= database.stat().st_size <= 20 * 1024**3:
        raise ValueError("SQLite size limit")
    with database.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3\x00":
            raise ValueError("Invalid SQLite signature")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("SQLite integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("SQLite foreign keys failed")
        record = connection.execute(
            "SELECT evidence_json FROM gas_retail_loads WHERE load_id=? AND length(evidence_json)<=?",
            (load_id, MAX_BYTES),
        ).fetchone()
        if record is None:
            raise ValueError("Missing or oversized revision")
        evidence = Evidence.model_validate_json(record[0])
        if revision_id(evidence) != load_id:
            raise ValueError("Stored manifest does not match the requested revision")
        counts = verify_load(connection, evidence)
        if output is None:
            return counts
        if output.exists():
            raise FileExistsError("Refusing to overwrite an export directory")
        statements = [
            "-- Private gas retail evidence; reuse review pending. Explicit import only.",
            r"\set ON_ERROR_STOP on",
            r"\encoding UTF8",
            r"\echo Iniciando carga masiva de gas; los datos se confirmaran al final.",
            "BEGIN;",
            "SET LOCAL search_path = public;",
            "SET LOCAL standard_conforming_strings = on;",
            "SET LOCAL lock_timeout = '10s';",
            "SET LOCAL statement_timeout = '10min';",
            "CREATE TEMP TABLE gas_retail_import_assert (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;",
        ]
        for table in TABLES:
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            rows = connection.execute(f"SELECT * FROM {table} WHERE load_id=?", (load_id,)).fetchall()
            # imported_at is the destination's first import timestamp, not a content revision field.
            content_columns = [column for column in columns if column != "imported_at"]
            projection = ",".join(content_columns)
            stage = f"stage_{table}"
            statements.extend(
                [
                    f"\\echo Cargando {table}: {len(rows)} filas",
                    f"CREATE TEMP TABLE {stage} (LIKE {table}) ON COMMIT DROP;",
                    f"COPY {stage} ({','.join(columns)}) FROM STDIN;",
                ]
            )
            for row in rows:
                statements.append("\t".join(copy_field(value) for value in row))
            statements.extend(
                [
                    r"\.",
                    f"\\echo Verificando {table}",
                    f"INSERT INTO {table} ({','.join(columns)}) SELECT {','.join(columns)} FROM {stage} "
                    "ON CONFLICT DO NOTHING;",
                    # EXCEPT ALL compares NULLs and multiplicity, without repeating every literal over the wire.
                    "INSERT INTO gas_retail_import_assert SELECT NOT EXISTS ("
                    f"SELECT {projection} FROM {stage} EXCEPT ALL SELECT {projection} FROM {table} "
                    f"WHERE load_id={literal(load_id)});",
                ]
            )
            statements.append(
                f"INSERT INTO gas_retail_import_assert SELECT COUNT(*) = {len(rows)} FROM {table} "
                f"WHERE load_id={literal(load_id)};"
            )
        statements.extend([r"\echo Confirmando transaccion...", "COMMIT;", r"\echo Carga masiva confirmada."])
        output.mkdir(parents=True)
        (output / "schema.sql").write_text(
            "BEGIN;\nSET LOCAL search_path = public;\nSET LOCAL lock_timeout = '10s';\n"
            + schema_sql()
            + "\nALTER TABLE gas_retail_entities DROP CONSTRAINT IF EXISTS gas_retail_entities_kind_check;\n"
            + "ALTER TABLE gas_retail_entities ADD CONSTRAINT gas_retail_entities_kind_check "
            + "CHECK (kind IN ('retailer','group','rest','total','direct_consumer','unknown'));\n"
            + "ALTER TABLE gas_retail_mappings DROP CONSTRAINT IF EXISTS "
            + "gas_retail_mappings_load_id_source_id_observed_name_key;\n"
            + "CREATE UNIQUE INDEX IF NOT EXISTS gas_retail_mappings_name_identity_idx "
            + "ON gas_retail_mappings(load_id,source_id,observed_name,gas_id);\nCOMMIT;\n"
        )
        (output / "data.sql").write_text("\n".join(statements) + "\n")
        (output / "verification.json").write_text(json.dumps({"load_id": load_id, "counts": counts}, indent=2) + "\n")
        return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--load-id", required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and args.output_dir is None:
        parser.error("Choose --dry-run or --output-dir")
    counts = export(args.database, args.load_id, None if args.dry_run else args.output_dir)
    print(json.dumps({"dry_run": args.dry_run, "counts": counts, "remote_writes": False}))


if __name__ == "__main__":
    main()

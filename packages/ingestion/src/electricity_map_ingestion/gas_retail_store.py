"""Append-only gas retail revisions within the importer's explicit transaction."""

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from importlib.resources import files
from typing import TYPE_CHECKING

from electricity_map_domain.gas_retail import MonthlyValue, QuarterlyValue, aggregate_quarter

if TYPE_CHECKING:
    from electricity_map_ingestion.gas_retail import Evidence

TABLES = (
    "gas_retail_loads",
    "gas_retail_sources",
    "gas_retail_entities",
    "gas_retail_mappings",
    "gas_retail_audits",
    "gas_retail_observations",
    "gas_retail_quarters",
    "gas_retail_catalogue",
    "gas_retail_source_audits",
    "gas_retail_unresolved_observations",
    "gas_retail_observation_details",
    "gas_retail_review_records",
)


def schema_sql() -> str:
    """The additive DDL is shared verbatim by SQLite and PostgreSQL."""
    return files("electricity_map_ingestion").joinpath("sql/gas_retail_v1.sql").read_text()


def canonical(evidence: Evidence) -> str:
    data = evidence.model_dump()
    if evidence.version == 1:
        for field in ("source_audits", "unresolved_observations", "observation_details", "review_records"):
            data.pop(field)
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def revision_id(evidence: Evidence) -> str:
    return hashlib.sha256(canonical(evidence).encode()).hexdigest()


def initialize(connection: sqlite3.Connection) -> None:
    for statement in schema_sql().split(";"):
        if statement.strip():
            connection.execute(statement)


def needs_entity_migration(connection: sqlite3.Connection) -> bool:
    rows = dict(
        connection.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table' "
            "AND name IN ('gas_retail_entities','gas_retail_mappings')"
        )
    )
    return ("gas_retail_entities" in rows and "direct_consumer" not in rows["gas_retail_entities"]) or (
        "gas_retail_mappings" in rows and "observed_name, gas_id)" not in rows["gas_retail_mappings"]
    )


def migrate_entities(connection: sqlite3.Connection) -> None:
    """Expand the CHECK inside the import transaction, preserving every revision.

    The caller disables SQLite foreign-key enforcement before BEGIN and runs
    foreign_key_check before committing, as required for a table rebuild.
    """
    for table in ("gas_retail_entities", "gas_retail_mappings"):
        statement = next(s for s in schema_sql().split(";") if f"CREATE TABLE IF NOT EXISTS {table} (" in s)
        connection.execute(statement.replace(f"IF NOT EXISTS {table} (", f"{table}_updated ("))
        connection.execute(f"INSERT INTO {table}_updated SELECT * FROM {table}")
        connection.execute(f"DROP TABLE {table}")
        connection.execute(f"ALTER TABLE {table}_updated RENAME TO {table}")


def rows_for_load(evidence: Evidence, imported_at: str) -> dict[str, list[tuple]]:
    load_id = revision_id(evidence)
    result = {table: [] for table in TABLES}
    result["gas_retail_loads"] = [
        (load_id, evidence.reviewed_on, imported_at, canonical(evidence), 0, "review_pending")
    ]
    for attribute, table in (
        ("sources", "gas_retail_sources"),
        ("entities", "gas_retail_entities"),
        ("mappings", "gas_retail_mappings"),
        ("observations", "gas_retail_observations"),
        ("catalogue", "gas_retail_catalogue"),
        ("unresolved_observations", "gas_retail_unresolved_observations"),
        ("observation_details", "gas_retail_observation_details"),
        ("review_records", "gas_retail_review_records"),
    ):
        for row in getattr(evidence, attribute):
            result[table].append((load_id, *row.model_dump().values()))
    for row in evidence.audits:
        result["gas_retail_audits"].append(
            (load_id, row.period, row.metric, row.status, json.dumps(row.source_ids), json.dumps(row.pages), row.note)
        )
    for row in evidence.source_audits:
        result["gas_retail_source_audits"].append(
            (
                load_id,
                row.source_id,
                row.period,
                row.metric,
                row.status,
                json.dumps(row.pages),
                row.table_review_status,
                row.retailer_coverage,
                row.geographic_scope,
                row.note,
            )
        )
    groups = defaultdict(list)
    mappings = {row.mapping_id: row for row in evidence.mappings}
    for row in evidence.observations:
        period = f"{row.month[:4]}T{(int(row.month[-2:]) - 1) // 3 + 1}"
        key = row.source_id, mappings[row.mapping_id].gas_id, period, row.metric, row.scope, row.unit
        groups[key].append(row)
    unresolved = defaultdict(list)
    for row in evidence.unresolved_observations:
        key = row.source_id, mappings[row.mapping_id].gas_id, row.period, row.metric, row.scope, row.unit
        unresolved[key].append(row)
        groups.setdefault(key, [])
    for key, rows in sorted(groups.items()):
        month_counts = Counter(row.month for row in rows)
        aggregate = aggregate_quarter(
            key[2],
            key[3],
            [
                MonthlyValue(
                    row.month,
                    row.status,
                    Decimal(row.value) if row.value is not None else None,
                    Decimal(row.upper_bound) if row.upper_bound is not None else None,
                )
                for row in rows
                if month_counts[row.month] == 1
            ],
        )
        final_month = f"{key[2][:4]}-{int(key[2][-1]) * 3:02}"
        if any(count > 1 for month, count in month_counts.items() if key[3] == "sales" or month == final_month):
            # Preserve every source row, but refuse to silently sum duplicate cells.
            aggregate = QuarterlyValue("source_error", None, None, (), tuple(row.status for row in rows))
        provenance = sorted(rows, key=lambda row: row.month)
        if evidence.version == 2 and key[3] == "clients":
            provenance = [row for row in provenance if row.month == final_month]
        result["gas_retail_quarters"].append(
            (
                load_id,
                *key,
                aggregate.status,
                str(aggregate.value) if aggregate.value is not None else None,
                str(aggregate.upper_bound) if aggregate.upper_bound is not None else None,
                json.dumps(aggregate.missing_months),
                json.dumps(aggregate.input_statuses),
                json.dumps(
                    [row.observation_id for row in provenance] + [row.observation_id for row in unresolved[key]]
                ),
            )
        )
    return result


def verify_load(connection: sqlite3.Connection, evidence: Evidence) -> dict[str, int]:
    load_id = revision_id(evidence)
    stored = connection.execute("SELECT imported_at FROM gas_retail_loads WHERE load_id=?", (load_id,)).fetchone()
    if stored is None:
        raise ValueError("Revision is missing")
    expected = rows_for_load(evidence, stored[0])
    for table, rows in expected.items():
        actual = connection.execute(f"SELECT * FROM {table} WHERE load_id=?", (load_id,)).fetchall()
        if len(actual) != len(rows) or set(actual) != set(rows):
            raise ValueError(f"Stored immutable revision differs in {table}")
    return {table: len(rows) for table, rows in expected.items()}


def write_load(connection: sqlite3.Connection, evidence: Evidence) -> str:
    load_id = revision_id(evidence)
    if connection.execute("SELECT 1 FROM gas_retail_loads WHERE load_id=?", (load_id,)).fetchone():
        verify_load(connection, evidence)
        return load_id
    rows = rows_for_load(evidence, datetime.now(UTC).isoformat())
    for table, values in rows.items():
        if values:
            placeholders = ",".join("?" for _ in values[0])
            connection.executemany(f"INSERT INTO {table} VALUES ({placeholders})", values)
    verify_load(connection, evidence)
    return load_id

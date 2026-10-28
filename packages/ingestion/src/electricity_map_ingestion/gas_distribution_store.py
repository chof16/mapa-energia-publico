"""Append gas network evidence in the caller's explicit transaction."""

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from electricity_map_ingestion.gas_distribution import NetworkRow


def initialize(connection: sqlite3.Connection) -> None:
    for statement in files("electricity_map_ingestion").joinpath("sql/gas_distribution_v1.sql").read_text().split(";"):
        if statement.strip():
            connection.execute(statement)


def write_load(connection: sqlite3.Connection, rows: Sequence[NetworkRow], sha256: str) -> str:
    from electricity_map_ingestion.gas_distribution import DOWNLOAD_URL, PERIOD, PUBLISHED_ON, SOURCE_URL, TITLE

    if connection.execute("SELECT 1 FROM gas_network_loads WHERE load_id=?", (sha256,)).fetchone():
        return sha256
    connection.execute(
        "INSERT INTO gas_network_loads VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            sha256,
            PERIOD,
            SOURCE_URL,
            DOWNLOAD_URL,
            TITLE,
            PUBLISHED_ON,
            datetime.now(UTC).isoformat(),
            sha256,
            "review_pending",
            len(rows),
        ),
    )
    connection.executemany(
        "INSERT INTO gas_network_rows VALUES (?,?,?,?,?,?)",
        [
            (
                sha256,
                row.source_row_id,
                row.province_code,
                row.municipality_name,
                row.distributor_name,
                row.supply_points,
            )
            for row in rows
        ],
    )
    return sha256

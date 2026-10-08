"""Read-only SQLAlchemy engine and request-scoped sessions."""

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import turso_serverless
from fastapi import Request
from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.dialects import registry
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from electricity_map_api.exceptions import DatabaseUnavailable


def create_database_engine(path: Path | None) -> Engine | None:
    if path is None:
        return None
    url = URL.create(
        "sqlite+pysqlite",
        database=f"file:{quote(str(path.resolve()))}",
        query={"mode": "ro", "uri": "true"},
    )
    # No persistent handles: each request sees newly published database snapshots.
    engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def configure_connection(connection, connection_record) -> None:
        connection.execute("PRAGMA query_only = ON")
        # A transaction spans all SELECTs in a response, including its source metadata.
        connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def begin_transaction(connection) -> None:
        connection.exec_driver_sql("BEGIN")

    return engine


def create_turso_engine(url: str | None, auth_token: str | None) -> Engine | None:
    """Open a remote connection per request; the token must grant read-only access."""
    if url is None:
        return None
    if not auth_token:
        raise ValueError("Turso auth token is required")
    registry.register("sqlite.turso_serverless", "electricity_map_api.turso", "TursoServerlessDialect")
    engine = create_engine(
        "sqlite+turso_serverless://",
        creator=lambda: turso_serverless.connect(url, auth_token=auth_token, isolation_level=None),
        poolclass=NullPool,
    )

    @event.listens_for(engine, "begin")
    def begin_transaction(connection) -> None:
        connection.exec_driver_sql("BEGIN")

    return engine


def get_session(request: Request) -> Iterator[Session]:
    engine: Engine | None = request.app.state.database_engine
    if engine is None:
        raise DatabaseUnavailable
    try:
        # One session per request, never shared by simultaneous requests.
        with Session(engine, autoflush=False) as session:
            yield session
    except SQLAlchemyError as error:
        raise DatabaseUnavailable from error


def get_distribution_session(request: Request) -> Iterator[Session]:
    """Keep the distribution error contract while sharing the connection lifecycle."""
    try:
        yield from get_session(request)
    except DatabaseUnavailable as error:
        raise DatabaseUnavailable("Distribution database is unavailable") from error

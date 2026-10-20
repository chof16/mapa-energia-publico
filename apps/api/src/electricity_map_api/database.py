"""Read-only SQLAlchemy engine and request-scoped sessions."""

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

from fastapi import Request
from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from electricity_map_api.exceptions import DatabaseUnavailable


def create_postgres_engine(url: str) -> Engine:
    """Use snapshot-consistent read-only transactions, including through PgBouncer."""
    parsed = make_url(url).set(drivername="postgresql+psycopg")
    engine = create_engine(
        parsed,
        connect_args={"connect_timeout": 15, "prepare_threshold": None},
        pool_size=5,
        max_overflow=0,
        pool_timeout=15,
        pool_pre_ping=True,
        isolation_level="REPEATABLE READ",
        execution_options={"postgresql_readonly": True},
        hide_parameters=True,
    )

    @event.listens_for(engine, "begin")
    def configure_transaction(connection) -> None:
        # Transaction-local settings work with Neon pooled URLs; startup options do not.
        connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")

    return engine


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

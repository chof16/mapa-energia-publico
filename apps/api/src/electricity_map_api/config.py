"""Application-wide settings loaded from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def _postgres_database() -> str | None:
    value = os.getenv("MAPA_DATABASE_URL") or None
    if value:
        try:
            parsed = make_url(value)
            valid = (
                parsed.drivername in {"postgres", "postgresql", "postgresql+psycopg"}
                and parsed.host
                and parsed.database
                and (parsed.port is None or 0 < parsed.port <= 65535)
            )
        except (ValueError, TypeError, ArgumentError):
            # SQLAlchemy parse errors may embed credentials: never forward them.
            valid = False
        if not valid:
            raise ValueError("MAPA_DATABASE_URL must be a PostgreSQL URL with a host and database")
    return value


def _positive_integer(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def _redis_url() -> str | None:
    value = os.getenv("MAPA_REDIS_URL") or None
    if value:
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme in {"redis", "rediss"}
                and parsed.hostname
                and (parsed.port is None or parsed.port > 0)
                and (
                    parsed.path in {"", "/"}
                    or (parsed.path.removeprefix("/").isascii() and parsed.path.removeprefix("/").isdigit())
                )
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("MAPA_REDIS_URL must be a redis:// or rediss:// URL with an optional database number")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Security and rate-limit settings for one API instance."""

    request_limit: int = 30
    window_seconds: int = 60
    database: Path | None = None
    development_mode: bool = False
    cors_origins: tuple[str, ...] = ()
    redis_url: str | None = field(default=None, repr=False)
    cache_ttl_seconds: int = 300
    database_url: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls) -> Settings:
        environment = os.getenv("ENV", "production")
        if environment not in {"development", "production"}:
            raise ValueError("ENV must be development or production")
        development_mode = environment == "development"
        database_url = _postgres_database()
        local_path = os.getenv("MAPA_DATABASE") if development_mode and not database_url else None
        if local_path and "://" in local_path:
            raise ValueError("MAPA_DATABASE is a SQLite path; use MAPA_DATABASE_URL for PostgreSQL")
        database = Path(local_path) if local_path else None
        default_origins = "http://localhost:5174,http://127.0.0.1:5174" if development_mode else ""
        cors_origins = tuple(
            origin.strip().rstrip("/")
            for origin in os.getenv("MAPA_CORS_ORIGINS", default_origins).split(",")
            if origin.strip()
        )
        for origin in cors_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("MAPA_CORS_ORIGINS must contain only HTTP(S) origins")
        return cls(
            request_limit=30 if development_mode else _positive_integer("MAPA_API_REQUEST_LIMIT", 30),
            window_seconds=60 if development_mode else _positive_integer("MAPA_API_WINDOW_SECONDS", 60),
            database=database,
            database_url=database_url,
            development_mode=development_mode,
            cors_origins=cors_origins,
            redis_url=_redis_url(),
            cache_ttl_seconds=_positive_integer("MAPA_CACHE_TTL_SECONDS", 300),
        )

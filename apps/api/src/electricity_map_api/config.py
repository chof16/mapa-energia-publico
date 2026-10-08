"""Application-wide settings loaded from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


def _positive_integer(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def _turso_database() -> tuple[str | None, str | None]:
    url = os.getenv("MAPA_TURSO_URL") or None
    token = os.getenv("MAPA_TURSO_AUTH_TOKEN") or None
    if bool(url) != bool(token):
        raise ValueError("MAPA_TURSO_URL and MAPA_TURSO_AUTH_TOKEN must be set together")
    if url:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"turso", "libsql", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("MAPA_TURSO_URL must use turso://, libsql:// or https:// without credentials or a path")
    return url, token


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
    turso_url: str | None = None
    turso_auth_token: str | None = field(default=None, repr=False)
    cors_origins: tuple[str, ...] = ()
    redis_url: str | None = field(default=None, repr=False)
    cache_ttl_seconds: int = 300

    @classmethod
    def from_environment(cls) -> Settings:
        environment = os.getenv("ENV", "production")
        if environment not in {"development", "production"}:
            raise ValueError("ENV must be development or production")
        development_mode = environment == "development"
        turso_url, turso_auth_token = (None, None) if development_mode else _turso_database()
        database = Path(value) if development_mode and (value := os.getenv("MAPA_DATABASE")) else None
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
            development_mode=development_mode,
            turso_url=turso_url,
            turso_auth_token=turso_auth_token,
            cors_origins=cors_origins,
            redis_url=_redis_url(),
            cache_ttl_seconds=_positive_integer("MAPA_CACHE_TTL_SECONDS", 300),
        )

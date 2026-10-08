"""Response cache contracts: no SQL on hits, isolation, expiry and failure recovery."""

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import pytest
from electricity_map_api.cache import MAX_RESPONSE_BYTES, RedisResponseCache
from electricity_map_api.config import Settings
from electricity_map_api.distribution.store import build_database
from electricity_map_api.main import create_app
from electricity_map_api.market.schemas import QuartersResponse
from electricity_map_ingestion.market_store import initialize, write_quarter
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from sqlalchemy import event


class MemoryRedis:
    def __init__(self):
        self.now = 0
        self.values = {}
        self.closed = False

    def get(self, key):
        payload, expiry = self.values.get(key, (None, 0))
        return payload if expiry > self.now else None

    def set(self, key, payload, *, ex):
        self.values[key] = (payload, self.now + ex)

    def close(self):
        self.closed = True


@pytest.fixture
def cached_app(tmp_path):
    database = tmp_path / "cache.sqlite"
    with sqlite3.connect(database) as connection:
        initialize(connection)
        write_quarter(
            connection,
            (
                "electricity",
                "2024T4",
                "package",
                "resource",
                "revision-1",
                0,
                "now",
                "https://example.org",
                "license",
                "https://example.org/license",
                "https://example.org/terms",
                "Source",
            ),
            [],
        )
    build_database(database)
    app = create_app(Settings(database=database, development_mode=True, cors_origins=("https://example.org",)))
    app.state.response_cache = RedisResponseCache(MemoryRedis(), str(database), 300)
    return app, database


@pytest.mark.parametrize(
    "url",
    [
        "/v1/market/quarters",
        "/v1/market/shares?period=2024T4",
        "/v1/market/series/R2-001",
        "/v1/market/share-series/R2-001",
        "/v1/market/communities/R2-001?period=2024T4",
        "/v1/distribution/provinces",
        "/v1/distribution/provinces/28",
    ],
)
def test_hit_does_not_open_a_database_connection(cached_app, url):
    app, _ = cached_app
    client = TestClient(app)
    first = client.get(url)
    assert first.status_code == 200
    assert first.headers["x-cache"] == "MISS"

    @event.listens_for(app.state.database_engine, "connect")
    def prohibit_sql(connection, record):
        pytest.fail("A cache hit must not contact the database")

    second = client.get(url, headers={"Origin": "https://example.org"})
    assert second.headers["x-cache"] == "HIT"
    assert second.headers["access-control-allow-origin"] == "https://example.org"
    assert second.json() == first.json()


def test_expiry_refreshes_data_and_metadata_together(cached_app):
    app, database = cached_app
    client = TestClient(app)
    url = "/v1/market/shares?period=2024T4"
    assert client.get(url).json()["metadata_modified"] == "revision-1"
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE loads SET metadata_modified='revision-2'")
    assert client.get(url).json()["metadata_modified"] == "revision-1"
    app.state.response_cache.client.now += 301
    response = client.get(url)
    assert response.headers["x-cache"] == "MISS"
    assert response.json()["metadata_modified"] == "revision-2"


def test_filters_path_and_query_defaults_have_independent_keys(cached_app):
    app, _ = cached_app
    client = TestClient(app)
    assert client.get("/v1/market/shares?period=2024T4").headers["x-cache"] == "MISS"
    assert (
        client.get("/v1/market/shares?sector=electricity&period=2024T4&offset=0&limit=50").headers["x-cache"] == "HIT"
    )
    for suffix in ("&community_code=13", "&limit=1", "&offset=1"):
        assert client.get("/v1/market/shares?period=2024T4" + suffix).headers["x-cache"] == "MISS"
    for code in ("R2-001", "R2-002"):
        assert client.get(f"/v1/market/share-series/{code}").headers["x-cache"] == "MISS"
    assert client.get("/v1/market/series/R2-001").headers["x-cache"] == "MISS"
    assert client.get("/v1/market/quarters?sector=gas").json()["quarters"] == []


def test_errors_are_not_cached_and_cache_hits_still_consume_quota(cached_app):
    app, _ = cached_app
    client = TestClient(app)
    for _ in range(2):
        assert client.get("/v1/market/shares?period=2025T4").status_code == 404
        assert client.get("/v1/market/shares?period=invalid").status_code == 422
    assert not app.state.response_cache.client.values
    app.state.settings = replace(app.state.settings, development_mode=False, request_limit=2)
    assert client.get("/v1/market/quarters").headers["x-cache"] == "MISS"
    assert client.get("/v1/market/quarters").headers["x-cache"] == "HIT"
    assert client.get("/v1/market/quarters").status_code == 429


def test_redis_outage_bypasses_cache_without_exposing_credentials(cached_app, monkeypatch, caplog):
    app, _ = cached_app
    calls = []

    def unavailable(key):
        calls.append(key)
        raise ConnectionError("redis://secret@example.org")

    monkeypatch.setattr(app.state.response_cache.client, "get", unavailable)
    client = TestClient(app)
    for _ in range(2):
        response = client.get("/v1/market/quarters")
        assert response.status_code == 200
        assert response.headers["x-cache"] == "BYPASS"
    assert len(calls) == 1
    assert "secret" not in caplog.text


@pytest.mark.parametrize("payload", [b"not json", b'{"sector":"invalid"}', b"x" * (MAX_RESPONSE_BYTES + 1)])
def test_invalid_cached_response_is_replaced(cached_app, payload):
    app, _ = cached_app
    client = TestClient(app)
    original = client.get("/v1/market/quarters").json()
    store = app.state.response_cache.client.values
    key = next(iter(store))
    store[key] = (payload, 300)
    result = client.get("/v1/market/quarters")
    assert result.headers["x-cache"] == "MISS"
    assert result.json() == original


def test_simultaneous_misses_only_load_once_and_sources_are_isolated():
    backend = MemoryRedis()
    cache = RedisResponseCache(backend, "source-one")
    started, release = Event(), Event()
    calls = []

    def load():
        calls.append(1)
        started.set()
        assert release.wait(5)
        return QuartersResponse(sector="electricity", quarters=[])

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(cache.load, "quarters", QuartersResponse, load) for _ in range(8)]
        assert started.wait(5)
        release.set()
        statuses = [future.result(timeout=5)[1] for future in futures]
    assert len(calls) == 1
    assert statuses.count("MISS") == 1
    assert statuses.count("HIT") == 7
    other = RedisResponseCache(backend, "source-two")
    assert other.load("quarters", QuartersResponse, load)[1] == "MISS"


def test_real_redis_shared_between_application_instances(cached_app):
    url = os.getenv("TEST_REDIS_URL")
    if not url:
        pytest.skip("Set TEST_REDIS_URL to exercise a local Redis server")
    _, database = cached_app
    settings = Settings(database=database, development_mode=True, redis_url=url, cache_ttl_seconds=30)
    with TestClient(create_app(settings)) as first, TestClient(create_app(settings)) as second:
        assert first.get("/v1/market/quarters").headers["x-cache"] == "MISS"

        @event.listens_for(second.app.state.database_engine, "connect")
        def prohibit_sql(connection, record):
            pytest.fail("A shared Redis hit must not contact the database")

        assert second.get("/v1/market/quarters").headers["x-cache"] == "HIT"
        backend = first.app.state.response_cache
        for key in backend.client.scan_iter(match=backend.prefix + "*"):
            assert 0 < backend.client.ttl(key) <= 30
            backend.client.delete(key)


@pytest.mark.parametrize(
    "url", ["http://example.org", "redis:///0", "redis://example.org/nope", "redis://example.org?socket_timeout=90"]
)
def test_redis_settings_reject_invalid_urls_without_echoing_them(monkeypatch, url):
    monkeypatch.setenv("MAPA_REDIS_URL", url)
    with pytest.raises(ValueError, match="MAPA_REDIS_URL") as error:
        Settings.from_environment()
    assert url not in str(error.value)


def test_redis_settings_keep_credentials_private(monkeypatch):
    monkeypatch.setenv("MAPA_REDIS_URL", "rediss://default:secret@example.org:6379/0")
    monkeypatch.setenv("MAPA_CACHE_TTL_SECONDS", "120")
    settings = Settings.from_environment()
    assert settings.redis_url.endswith("/0")
    assert settings.cache_ttl_seconds == 120
    assert "secret" not in repr(settings)

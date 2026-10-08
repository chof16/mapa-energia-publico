"""Public endpoints retain IP quotas without API-key authentication."""

from types import SimpleNamespace

import pytest
from electricity_map_api import rate_limit
from electricity_map_api.config import Settings
from electricity_map_api.main import create_app
from fastapi.testclient import TestClient


def test_health_does_not_consume_quota() -> None:
    client = TestClient(create_app(Settings(request_limit=1)))
    for _ in range(3):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "X-RateLimit-Limit" not in response.headers
    assert client.get("/v1").status_code == 200


def test_api_keys_neither_authenticate_nor_bypass_ip_quota() -> None:
    client = TestClient(create_app(Settings(request_limit=2)))
    for key in ("old-key", "arbitrary-value"):
        response = client.get("/v1", headers={"X-API-Key": key})
        assert response.status_code == 200
        assert "authenticated" not in response.json()
        assert response.headers["X-RateLimit-Limit"] == "2"
    response = client.get("/v1")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert client.get("/v1", headers={"X-API-Key": "different-key"}).status_code == 429


def test_quota_is_scoped_to_client_address() -> None:
    app = create_app(Settings(request_limit=1))
    first = TestClient(app, client=("192.0.2.1", 50000))
    second = TestClient(app, client=("192.0.2.2", 50001))
    assert first.get("/v1").status_code == 200
    assert first.get("/v1", headers={"X-Forwarded-For": "192.0.2.3"}).status_code == 429
    assert second.get("/v1").status_code == 200


def test_quota_resets_after_its_window(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 100.0
    monkeypatch.setattr(rate_limit, "time", SimpleNamespace(monotonic=lambda: now))
    client = TestClient(create_app(Settings(request_limit=1, window_seconds=60)))
    assert client.get("/v1").status_code == 200
    assert client.get("/v1").status_code == 429
    now += 60
    assert client.get("/v1").status_code == 200


def test_development_skips_ip_quota() -> None:
    client = TestClient(create_app(Settings(request_limit=1, development_mode=True)))
    for _ in range(3):
        response = client.get("/v1")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers


def test_development_environment_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENV", raising=False)
    assert Settings.from_environment().development_mode is False
    monkeypatch.setenv("ENV", "development")
    assert Settings.from_environment().development_mode is True
    monkeypatch.setenv("ENV", "production")
    assert Settings.from_environment().development_mode is False
    monkeypatch.setenv("ENV", "typo")
    with pytest.raises(ValueError, match="ENV"):
        Settings.from_environment()


def test_public_quota_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("MAPA_API_REQUEST_LIMIT", raising=False)
    monkeypatch.delenv("MAPA_API_WINDOW_SECONDS", raising=False)
    defaults = Settings.from_environment()
    assert (defaults.request_limit, defaults.window_seconds) == (30, 60)
    monkeypatch.setenv("MAPA_API_REQUEST_LIMIT", "45")
    assert Settings.from_environment().request_limit == 45
    monkeypatch.setenv("MAPA_API_REQUEST_LIMIT", "0")
    with pytest.raises(ValueError, match="MAPA_API_REQUEST_LIMIT"):
        Settings.from_environment()

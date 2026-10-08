"""Development defaults to localhost; production requires explicit origins."""

import pytest
from electricity_map_api.config import Settings
from electricity_map_api.main import create_app
from fastapi.testclient import TestClient


def test_development_defaults_to_localhost_without_quotas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("MAPA_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("MAPA_API_REQUEST_LIMIT", "invalid-limit")
    monkeypatch.setenv("MAPA_API_WINDOW_SECONDS", "invalid-window")
    settings = Settings.from_environment()
    assert settings.cors_origins == ("http://localhost:5174", "http://127.0.0.1:5174")
    client = TestClient(create_app(settings))
    for origin in settings.cors_origins:
        response = client.get("/v1", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert "X-RateLimit-Limit" not in response.headers


def test_development_can_override_local_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("MAPA_CORS_ORIGINS", "http://localhost:4173")
    client = TestClient(create_app(Settings.from_environment()))
    response = client.get("/v1", headers={"Origin": "http://localhost:4173"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4173"
    assert "access-control-allow-origin" not in client.get("/v1", headers={"Origin": "http://localhost:5174"}).headers


def test_production_cors_allows_only_configured_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("MAPA_CORS_ORIGINS", raising=False)
    assert Settings.from_environment().cors_origins == ()
    monkeypatch.setenv("MAPA_CORS_ORIGINS", "https://map.example")
    client = TestClient(create_app(Settings.from_environment()))
    headers = {"Origin": "https://map.example", "Access-Control-Request-Method": "GET"}
    allowed = client.options("/v1", headers=headers)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://map.example"
    denied = client.options("/v1", headers={**headers, "Origin": "https://other.example"})
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
    monkeypatch.setenv("MAPA_CORS_ORIGINS", "https://map.example/path")
    with pytest.raises(ValueError, match="MAPA_CORS_ORIGINS"):
        Settings.from_environment()

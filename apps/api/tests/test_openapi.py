"""Contract coverage for Swagger/ReDoc and runtime response validation."""

import pytest
from electricity_map_api.config import Settings
from electricity_map_api.main import create_app
from electricity_map_api.market import service
from fastapi.testclient import TestClient

RESPONSES = {
    "/healthz": "HealthResponse",
    "/v1": "MetadataResponse",
    "/v1/market/quarters": "QuartersResponse",
    "/v1/market/reference-marketers": "ReferenceMarketersResponse",
    "/v1/market/shares": "SharesResponse",
    "/v1/market/series/{marketer_code}": "SeriesResponse",
    "/v1/market/share-series/{marketer_code}": "ShareSeriesResponse",
    "/v1/market/communities/{marketer_code}": "CommunitySharesResponse",
    "/v1/distribution/provinces/{province_code}": "ProvincePresenceResponse",
    "/v1/distribution/provinces": "ProvincePresenceSummaryResponse",
}


def test_all_endpoints_publish_response_schemas_and_errors() -> None:
    client = TestClient(create_app(Settings()))
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == set(RESPONSES)
    for path, model in RESPONSES.items():
        operation = schema["paths"][path]["get"]
        responses = operation["responses"]
        assert responses["200"]["content"]["application/json"]["schema"] == {"$ref": f"#/components/schemas/{model}"}
        assert schema["components"]["schemas"][model]["required"]
        assert "requestBody" not in operation  # Read-only GETs accept path/query/header parameters.
        if path == "/healthz":
            continue
        assert "401" not in responses
        assert not operation.get("security")
        assert all(parameter["name"] != "X-API-Key" for parameter in operation.get("parameters", []))
        assert responses["429"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
        assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/ValidationErrorResponse")
        assert "Retry-After" in responses["429"]["headers"]
        if path.startswith("/v1/market") and path != "/v1/market/reference-marketers":
            assert "503" in responses
        if path.startswith("/v1/distribution"):
            assert "503" in responses
        if path == "/v1/market/reference-marketers":
            assert "503" not in responses
        if path in ("/v1/market/shares", "/v1/market/communities/{marketer_code}"):
            assert "404" in responses


def test_openapi_describes_input_constraints_and_nested_nullable_fields() -> None:
    schema = create_app(Settings()).openapi()
    operation = schema["paths"]["/v1/market/share-series/{marketer_code}"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert set(parameters) == {
        "marketer_code",
        "sector",
        "community_code",
        "start_period",
        "end_period",
        "limit",
        "offset",
    }
    assert parameters["marketer_code"]["required"] is True
    assert parameters["marketer_code"]["in"] == "path"
    assert parameters["marketer_code"]["schema"]["not"] == {"const": "R2-000"}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 120
    assert parameters["offset"]["schema"]["maximum"] == 10_000
    assert parameters["start_period"]["schema"]["anyOf"][0]["pattern"] == r"^20[0-9]{2}T[1-4]$"
    assert parameters["community_code"]["schema"]["anyOf"][0]["maxLength"] == 2
    schemas = schema["components"]["schemas"]
    assert schemas["EnergySector"]["enum"] == ["electricity", "gas"]
    properties = schemas["ShareSeriesPoint"]["properties"]
    assert {
        "supplies",
        "period",
        "source_url",
        "license_url",
        "metadata_modified",
        "package_name",
        "resource_id",
    } <= set(properties)
    assert {"type": "null"} in properties["share"]["anyOf"]
    assert {"type": "null"} in schemas["MarketerShare"]["properties"]["observed_name"]["anyOf"]
    assert schemas["SharesResponse"]["properties"]["items"]["items"]["$ref"].endswith("/MarketerShare")
    required_period = next(
        parameter
        for parameter in schema["paths"]["/v1/market/shares"]["get"]["parameters"]
        if parameter["name"] == "period"
    )
    assert required_period["required"] is True

    distribution = schema["paths"]["/v1/distribution/provinces/{province_code}"]["get"]
    distribution_parameters = {parameter["name"]: parameter for parameter in distribution["parameters"]}
    assert set(distribution_parameters) == {"province_code", "sector"}
    assert distribution_parameters["province_code"]["schema"]["pattern"].endswith("5[0-2])$")
    presence = schemas["ProvincePresenceResponse"]["properties"]
    assert presence["complete"]["const"] is False
    assert presence["items"]["items"]["$ref"].endswith("/DistributorPresence")
    assert "maxItems" not in presence["items"]
    summary_count = schemas["ProvincePresenceSummaryItem"]["properties"]["documented_distributor_count"]
    assert "maximum" not in summary_count
    assert {"type": "null"} in schemas["DistributorPresence"]["properties"]["cor"]["anyOf"]


def test_bad_service_output_is_rejected_at_http_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    from electricity_map_api.database import get_session

    app = create_app(Settings())
    app.dependency_overrides[get_session] = lambda: None
    monkeypatch.setattr(service, "quarters", lambda *_: {"sector": "electricity", "quarters": [{"period": "invalid"}]})
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/v1/market/quarters").status_code == 500

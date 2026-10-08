"""Health and API metadata response DTOs."""

from typing import Literal

from electricity_map_domain import EnergySector

from electricity_map_api.schemas import ResponseDTO


class HealthResponse(ResponseDTO):
    status: Literal["ok"]


class MetadataResponse(ResponseDTO):
    api: Literal["v1"]
    available_sector: EnergySector
    tiles: str

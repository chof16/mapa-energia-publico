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
    available_sectors: tuple[EnergySector, ...] = (EnergySector.ELECTRICITY, EnergySector.GAS)
    gas_distribution_api: Literal["/v1/gas/distribution"] = "/v1/gas/distribution"
    gas_retail_api: Literal["/v1/gas/retail"] = "/v1/gas/retail"
    gas_reference_marketers_api: Literal["/v1/gas/reference-marketers"] = "/v1/gas/reference-marketers"
    electricity_api: Literal["/v1/electricity"] = "/v1/electricity"

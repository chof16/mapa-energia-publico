"""Bounded, explicitly historical gas distributor map contracts."""

from typing import Annotated, Literal

from pydantic import Field

from electricity_map_api.schemas import Count, PageLimit, PageOffset, PageQuery, ResponseDTO

GasProvinceCode = Annotated[str, Field(pattern=r"^(?:0[1-9]|[1-4][0-9]|5[0-2])$")]
GasNetworkLoadId = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class GasNetworkQuery(PageQuery):
    load_id: GasNetworkLoadId | None = None


class GasNetworkSource(ResponseDTO):
    load_id: GasNetworkLoadId
    period: Annotated[str, Field(pattern=r"^\d{4}-(?:0[1-9]|1[0-2])$")]
    source_url: str
    download_url: str
    source_title: str
    published_on: str
    retrieved_at: str
    source_sha256: GasNetworkLoadId
    row_count: Count
    reuse_status: Literal["review_pending"]
    attribution: str = "Origen de los datos: Comisión Nacional de los Mercados y la Competencia"
    confidence: Literal["official_document"] = "official_document"
    network_scope: Literal["natural_gas_at_most_4_bar"] = "natural_gas_at_most_4_bar"


class GasNetworkProvince(ResponseDTO):
    province_code: GasProvinceCode
    documented_distributor_count: Count
    source_row_count: Count
    supply_points: Count


class GasNetworkDistributor(ResponseDTO):
    distributor_name: Annotated[str, Field(min_length=1, max_length=160)]
    source_row_count: Count
    supply_points: Count


class GasNetworkPage(ResponseDTO):
    sector: Literal["gas"] = "gas"
    scope: Literal["documented_provincial_presence"] = "documented_provincial_presence"
    complete: Literal[False] = False
    source: GasNetworkSource
    total: Count
    limit: PageLimit
    offset: PageOffset


class GasNetworkProvincesResponse(GasNetworkPage):
    items: list[GasNetworkProvince] = Field(max_length=100)


class GasNetworkDistributorsResponse(GasNetworkPage):
    province_code: GasProvinceCode
    items: list[GasNetworkDistributor] = Field(max_length=100)


class GasNetworkRevisionsResponse(ResponseDTO):
    total: Count
    limit: PageLimit
    offset: PageOffset
    items: list[GasNetworkSource] = Field(max_length=100)

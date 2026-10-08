"""Operational and version metadata endpoints."""

from electricity_map_domain import EnergySector
from fastapi import APIRouter, Depends

from electricity_map_api.metadata.schemas import HealthResponse, MetadataResponse
from electricity_map_api.rate_limit import RATE_LIMIT_RESPONSES, enforce_rate_limit
from electricity_map_api.schemas import VALIDATION_RESPONSES

router = APIRouter()


@router.get("/healthz", tags=["operations"], response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/v1",
    tags=["metadata"],
    response_model=MetadataResponse,
    dependencies=[Depends(enforce_rate_limit)],
    responses={**RATE_LIMIT_RESPONSES, **VALIDATION_RESPONSES},
)
async def api_root() -> MetadataResponse:
    return MetadataResponse(
        api="v1",
        available_sector=EnergySector.ELECTRICITY,
        tiles="PMTiles are published as versioned static artifacts.",
    )

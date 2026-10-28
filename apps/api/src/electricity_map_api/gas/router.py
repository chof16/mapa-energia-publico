"""Historical gas network presence with shared validation, caching and rate limits."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from electricity_map_api.cache import CachedResponse
from electricity_map_api.dependencies import DatabaseSession
from electricity_map_api.gas import service
from electricity_map_api.gas.schemas import (
    GasNetworkDistributorsResponse,
    GasNetworkProvincesResponse,
    GasNetworkQuery,
    GasNetworkRevisionsResponse,
    GasProvinceCode,
)
from electricity_map_api.rate_limit import RATE_LIMIT_RESPONSES, enforce_rate_limit
from electricity_map_api.schemas import VALIDATION_RESPONSES, ErrorResponse

router = APIRouter(
    prefix="/v1/gas/distribution",
    tags=["gas"],
    dependencies=[Depends(enforce_rate_limit)],
    responses={
        **RATE_LIMIT_RESPONSES,
        **VALIDATION_RESPONSES,
        404: {"model": ErrorResponse, "description": "Gas network source is not loaded"},
        503: {"model": ErrorResponse, "description": "Database or gas network schema is unavailable"},
    },
)


@router.get("/provinces", response_model=GasNetworkProvincesResponse)
def provinces(
    query: Annotated[GasNetworkQuery, Query()], session: DatabaseSession, cache: CachedResponse
) -> GasNetworkProvincesResponse:
    """Count observed distributor names by province; absence remains unknown."""
    return cache.load(
        "gas.distribution.provinces", query, GasNetworkProvincesResponse, lambda: service.provinces(session, query)
    )


@router.get("/provinces/{province_code}", response_model=GasNetworkDistributorsResponse)
def distributors(
    province_code: GasProvinceCode,
    query: Annotated[GasNetworkQuery, Query()],
    session: DatabaseSession,
    cache: CachedResponse,
) -> GasNetworkDistributorsResponse:
    """Names as observed in the chosen annex, without census or corporate-group joins."""
    return cache.load(
        "gas.distribution.distributors",
        query,
        GasNetworkDistributorsResponse,
        lambda: service.distributors(session, province_code, query),
        province_code=province_code,
    )


@router.get("/revisions", response_model=GasNetworkRevisionsResponse)
def revisions(
    query: Annotated[GasNetworkQuery, Query()], session: DatabaseSession, cache: CachedResponse
) -> GasNetworkRevisionsResponse:
    """Discover retained source loads and their actual reporting month."""
    return cache.load(
        "gas.distribution.revisions", query, GasNetworkRevisionsResponse, lambda: service.revisions(session, query)
    )

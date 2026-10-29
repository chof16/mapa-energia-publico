"""Read-only gas retail routes with the common cache and rate limiter."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from electricity_map_api.cache import CachedResponse
from electricity_map_api.dependencies import DatabaseSession
from electricity_map_api.gas.retail import schemas as dto
from electricity_map_api.gas.retail import service
from electricity_map_api.rate_limit import RATE_LIMIT_RESPONSES, enforce_rate_limit
from electricity_map_api.schemas import VALIDATION_RESPONSES, ErrorResponse

router = APIRouter(
    prefix="/v1/gas",
    tags=["gas retail"],
    dependencies=[Depends(enforce_rate_limit)],
    responses={
        **RATE_LIMIT_RESPONSES,
        **VALIDATION_RESPONSES,
        404: {"model": ErrorResponse, "description": "Gas retail revision or reviewed retailer unavailable"},
        503: {"model": ErrorResponse, "description": "Database, schema or bounded evidence unavailable"},
    },
)


@router.get("/retail/periods", response_model=dto.GasRetailPeriodsResponse)
def periods(
    query: Annotated[dto.GasRetailPeriodQuery, Query()], session: DatabaseSession, cache: CachedResponse
) -> dto.GasRetailPeriodsResponse:
    return cache.load(
        "gas.retail.periods.v4", query, dto.GasRetailPeriodsResponse, lambda: service.periods(session, query)
    )


@router.get("/retail/marketers", response_model=dto.GasRetailMarketersResponse)
def marketers(
    query: Annotated[dto.GasRetailMarketersQuery, Query()], session: DatabaseSession, cache: CachedResponse
) -> dto.GasRetailMarketersResponse:
    return cache.load(
        "gas.retail.marketers.v4", query, dto.GasRetailMarketersResponse, lambda: service.marketers(session, query)
    )


@router.get("/retail/series/{marketer_id}", response_model=dto.GasRetailSeriesResponse)
def series(
    marketer_id: dto.GasRetailId,
    query: Annotated[dto.GasRetailSeriesQuery, Query()],
    session: DatabaseSession,
    cache: CachedResponse,
) -> dto.GasRetailSeriesResponse:
    return cache.load(
        "gas.retail.series.v4",
        query,
        dto.GasRetailSeriesResponse,
        lambda: service.series(session, marketer_id, query),
        marketer_id=marketer_id,
    )


@router.get("/retail/revisions", response_model=dto.GasRetailRevisionsResponse)
def revisions(
    query: Annotated[dto.GasRetailPageQuery, Query()], session: DatabaseSession, cache: CachedResponse
) -> dto.GasRetailRevisionsResponse:
    return cache.load(
        "gas.retail.revisions", query, dto.GasRetailRevisionsResponse, lambda: service.revisions(session, query)
    )


@router.get("/reference-marketers", response_model=dto.GasReferenceMarketersResponse)
def reference_marketers(
    query: Annotated[dto.GasRetailPageQuery, Query()], session: DatabaseSession, cache: CachedResponse
) -> dto.GasReferenceMarketersResponse:
    return cache.load(
        "gas.reference-marketers",
        query,
        dto.GasReferenceMarketersResponse,
        lambda: service.reference_marketers(session, query),
    )

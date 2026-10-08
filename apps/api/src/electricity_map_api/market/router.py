"""HTTP routes: validate request DTOs, delegate queries, publish response DTOs."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from electricity_map_api.market import service
from electricity_map_api.market.dependencies import MarketSession
from electricity_map_api.market.reference_data import reference_marketers as reviewed_reference_marketers
from electricity_map_api.market.schemas import (
    CommunitySharesResponse,
    MarketerCode,
    QuarterQuery,
    QuartersResponse,
    ReferenceMarketersResponse,
    SectorQuery,
    SeriesQuery,
    SeriesResponse,
    ShareSeriesQuery,
    ShareSeriesResponse,
    SharesQuery,
    SharesResponse,
)
from electricity_map_api.rate_limit import RATE_LIMIT_RESPONSES, enforce_rate_limit
from electricity_map_api.schemas import VALIDATION_RESPONSES, ErrorResponse

router = APIRouter(
    prefix="/v1/market",
    tags=["market"],
    dependencies=[Depends(enforce_rate_limit)],
    responses={**RATE_LIMIT_RESPONSES, **VALIDATION_RESPONSES},
)
QUARTER_RESPONSES = {404: {"model": ErrorResponse, "description": "Quarter is not loaded"}}
DATABASE_RESPONSES = {503: {"model": ErrorResponse, "description": "Market database is unavailable"}}


@router.get("/reference-marketers", response_model=ReferenceMarketersResponse)
def reference_marketers(query: Annotated[SectorQuery, Query()]) -> ReferenceMarketersResponse:
    """List verified electricity CORs; distributor associations remain unknown."""
    return reviewed_reference_marketers(query.sector)


@router.get("/quarters", response_model=QuartersResponse, responses=DATABASE_RESPONSES)
def quarters(query: Annotated[SectorQuery, Query()], session: MarketSession) -> QuartersResponse:
    """List up to 120 loaded quarters, newest first, with source and revision metadata."""
    return service.quarters(session, query)


@router.get("/shares", response_model=SharesResponse, responses={**QUARTER_RESPONSES, **DATABASE_RESPONSES})
def shares(query: Annotated[SharesQuery, Query()], session: MarketSession) -> SharesResponse:
    """Rank registered marketers for one quarter; unknown parameters are rejected."""
    return service.shares(session, query)


@router.get("/series/{marketer_code}", response_model=SeriesResponse, responses=DATABASE_RESPONSES)
def series(
    marketer_code: MarketerCode, query: Annotated[SeriesQuery, Query()], session: MarketSession
) -> SeriesResponse:
    """Return supplies for observed quarters only, ordered oldest first (up to 120)."""
    return service.series(session, marketer_code, query)


@router.get("/share-series/{marketer_code}", response_model=ShareSeriesResponse, responses=DATABASE_RESPONSES)
def share_series(
    marketer_code: MarketerCode, query: Annotated[ShareSeriesQuery, Query()], session: MarketSession
) -> ShareSeriesResponse:
    """Return shares for loaded quarters; absent codes yield zero, zero denominators yield null."""
    return service.share_series(session, marketer_code, query)


@router.get(
    "/communities/{marketer_code}",
    response_model=CommunitySharesResponse,
    responses={**QUARTER_RESPONSES, **DATABASE_RESPONSES},
)
def community_shares(
    marketer_code: MarketerCode, query: Annotated[QuarterQuery, Query()], session: MarketSession
) -> CommunitySharesResponse:
    """Return a marketer's autonomous-community shares for one loaded quarter."""
    return service.community_shares(session, marketer_code, query)

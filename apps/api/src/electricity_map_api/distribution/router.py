"""HTTP endpoint for reviewed provincial distributor presence."""

from typing import Annotated

from electricity_map_domain import EnergySector
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from electricity_map_api.database import get_distribution_session
from electricity_map_api.distribution import service
from electricity_map_api.distribution.schemas import (
    ProvinceCode,
    ProvincePresenceResponse,
    ProvincePresenceSummaryResponse,
    ProvinceQuery,
)
from electricity_map_api.rate_limit import RATE_LIMIT_RESPONSES, enforce_rate_limit
from electricity_map_api.schemas import VALIDATION_RESPONSES, ErrorResponse

router = APIRouter(
    prefix="/v1/distribution",
    tags=["distribution"],
    dependencies=[Depends(enforce_rate_limit)],
    responses={**RATE_LIMIT_RESPONSES, **VALIDATION_RESPONSES},
)
DistributionSession = Annotated[Session, Depends(get_distribution_session)]
DATABASE_RESPONSES = {503: {"model": ErrorResponse, "description": "Distribution database is unavailable"}}


@router.get("/provinces", response_model=ProvincePresenceSummaryResponse, responses=DATABASE_RESPONSES)
def province_summary(
    query: Annotated[ProvinceQuery, Query()], session: DistributionSession
) -> ProvincePresenceSummaryResponse:
    """Summarize documented companies per province for an incomplete map layer."""
    return ProvincePresenceSummaryResponse(
        sector=query.sector,
        snapshot_date=service.snapshot_date(session),
        scope="documented_provincial_presence",
        complete=False,
        items=service.documented_provinces(session) if query.sector == EnergySector.ELECTRICITY else [],
    )


@router.get("/provinces/{province_code}", response_model=ProvincePresenceResponse, responses=DATABASE_RESPONSES)
def province_presence(
    province_code: ProvinceCode, query: Annotated[ProvinceQuery, Query()], session: DistributionSession
) -> ProvincePresenceResponse:
    """List verified presence, never a complete network or a municipality assignment."""
    return ProvincePresenceResponse(
        sector=query.sector,
        province_code=province_code,
        snapshot_date=service.snapshot_date(session),
        scope="provincial_presence",
        complete=False,
        items=service.presence_for_province(session, province_code) if query.sector == EnergySector.ELECTRICITY else [],
    )

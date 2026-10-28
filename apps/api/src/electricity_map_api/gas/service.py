"""Bounded mapped queries for explicit provincial summaries of network source rows."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from electricity_map_api.gas.exceptions import GasSourceNotLoaded
from electricity_map_api.gas.models import GasNetworkLoad, GasNetworkRow
from electricity_map_api.gas.schemas import (
    GasNetworkDistributor,
    GasNetworkDistributorsResponse,
    GasNetworkProvince,
    GasNetworkProvincesResponse,
    GasNetworkQuery,
    GasNetworkRevisionsResponse,
    GasNetworkSource,
)


def _source(session: Session, query: GasNetworkQuery) -> GasNetworkSource:
    statement = select(GasNetworkLoad)
    if query.load_id:
        statement = statement.where(GasNetworkLoad.load_id == query.load_id)
    row = session.scalar(
        statement.order_by(
            GasNetworkLoad.period.desc(), GasNetworkLoad.retrieved_at.desc(), GasNetworkLoad.load_id
        ).limit(1)
    )
    if row is None:
        raise GasSourceNotLoaded
    return GasNetworkSource.model_validate(row)


def provinces(session: Session, query: GasNetworkQuery) -> GasNetworkProvincesResponse:
    source = _source(session, query)
    filters = [GasNetworkRow.load_id == source.load_id]
    total = session.scalar(select(func.count(func.distinct(GasNetworkRow.province_code))).where(*filters))
    rows = session.execute(
        select(
            GasNetworkRow.province_code,
            func.count(func.distinct(GasNetworkRow.distributor_name)),
            func.count(),
            func.sum(GasNetworkRow.supply_points),
        )
        .where(*filters)
        .group_by(GasNetworkRow.province_code)
        .order_by(GasNetworkRow.province_code)
        .limit(query.limit)
        .offset(query.offset)
    )
    return GasNetworkProvincesResponse(
        source=source,
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=[
            GasNetworkProvince(
                province_code=code, documented_distributor_count=count, source_row_count=row_count, supply_points=points
            )
            for code, count, row_count, points in rows
        ],
    )


def distributors(session: Session, province_code: str, query: GasNetworkQuery) -> GasNetworkDistributorsResponse:
    source = _source(session, query)
    filters = [GasNetworkRow.load_id == source.load_id, GasNetworkRow.province_code == province_code]
    total = session.scalar(select(func.count(func.distinct(GasNetworkRow.distributor_name))).where(*filters))
    rows = session.execute(
        select(GasNetworkRow.distributor_name, func.count(), func.sum(GasNetworkRow.supply_points))
        .where(*filters)
        .group_by(GasNetworkRow.distributor_name)
        .order_by(GasNetworkRow.distributor_name)
        .limit(query.limit)
        .offset(query.offset)
    )
    return GasNetworkDistributorsResponse(
        province_code=province_code,
        source=source,
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=[
            GasNetworkDistributor(distributor_name=name, source_row_count=count, supply_points=points)
            for name, count, points in rows
        ],
    )


def revisions(session: Session, query: GasNetworkQuery) -> GasNetworkRevisionsResponse:
    filters = [GasNetworkLoad.load_id == query.load_id] if query.load_id else []
    total = session.scalar(select(func.count()).select_from(GasNetworkLoad).where(*filters))
    rows = session.scalars(
        select(GasNetworkLoad)
        .where(*filters)
        .order_by(GasNetworkLoad.period.desc(), GasNetworkLoad.retrieved_at.desc(), GasNetworkLoad.load_id)
        .limit(query.limit)
        .offset(query.offset)
    )
    return GasNetworkRevisionsResponse(
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=[GasNetworkSource.model_validate(row) for row in rows],
    )

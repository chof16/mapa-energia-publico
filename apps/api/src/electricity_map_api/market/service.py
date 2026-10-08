"""Bounded ORM queries over imported market data, independent of HTTP routing."""

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, aliased

from electricity_map_api.market.exceptions import QuarterNotLoaded
from electricity_map_api.market.models import MarketLoad, MarketRow
from electricity_map_api.market.schemas import (
    CommunityShare,
    CommunitySharesResponse,
    MarketerShare,
    Quarter,
    QuarterQuery,
    QuartersResponse,
    RevisionMetadata,
    SectorQuery,
    SeriesQuery,
    SeriesResponse,
    ShareSeriesPoint,
    ShareSeriesQuery,
    ShareSeriesResponse,
    SharesQuery,
    SharesResponse,
    SourceMetadata,
    SuppliesPoint,
)


def _load(session: Session, query: QuarterQuery) -> MarketLoad:
    load = session.get(MarketLoad, (query.sector, query.period))
    if load is None:
        raise QuarterNotLoaded
    return load


def _category_total(category: str):
    return func.coalesce(func.sum(case((MarketRow.category == category, MarketRow.supplies), else_=0)), 0)


def _category_columns():
    return (
        _category_total("marketer").label("marketer_supplies"),
        _category_total("direct_consumer").label("direct_consumer_supplies"),
        _category_total("unavailable").label("unavailable_supplies"),
    )


def quarters(session: Session, query: SectorQuery) -> QuartersResponse:
    loads = session.scalars(
        select(MarketLoad).where(MarketLoad.sector == query.sector).order_by(MarketLoad.period.desc()).limit(120)
    )
    return QuartersResponse(sector=query.sector, quarters=[Quarter.model_validate(load) for load in loads])


def shares(session: Session, query: SharesQuery) -> SharesResponse:
    load = _load(session, query)
    conditions = [MarketRow.sector == query.sector, MarketRow.period == query.period]
    if query.community_code is not None:
        conditions.append(MarketRow.community_code == query.community_code)
    totals = session.execute(select(*_category_columns()).where(*conditions)).mappings().one()
    supplies = func.sum(MarketRow.supplies).label("supplies")
    rows = session.execute(
        select(MarketRow.marketer_code, func.max(MarketRow.marketer_name).label("observed_name"), supplies)
        .where(*conditions, MarketRow.category == "marketer")
        .group_by(MarketRow.marketer_code)
        .order_by(supplies.desc(), MarketRow.marketer_code)
        .limit(query.limit)
        .offset(query.offset)
    ).mappings()
    return SharesResponse(
        **RevisionMetadata.model_validate(load).model_dump(),
        **totals,
        sector=query.sector,
        period=query.period,
        community_code=query.community_code,
        denominator="supplies_with_registered_marketer",
        items=[
            MarketerShare(
                **row, share=row["supplies"] / totals["marketer_supplies"] if totals["marketer_supplies"] else 0
            )
            for row in rows
        ],
    )


def series(session: Session, marketer_code: str, query: SeriesQuery) -> SeriesResponse:
    conditions = [MarketRow.sector == query.sector, MarketRow.marketer_code == marketer_code]
    if query.community_code is not None:
        conditions.append(MarketRow.community_code == query.community_code)
    rows = session.execute(
        select(MarketRow.period, func.sum(MarketRow.supplies).label("supplies"), MarketLoad.metadata_modified)
        .join(MarketLoad, and_(MarketLoad.sector == MarketRow.sector, MarketLoad.period == MarketRow.period))
        .where(*conditions)
        .group_by(MarketRow.period, MarketLoad.metadata_modified)
        .order_by(MarketRow.period)
        .limit(120)
    ).mappings()
    points = [SuppliesPoint.model_validate(row) for row in rows]
    source = session.scalars(
        select(MarketLoad).where(MarketLoad.sector == query.sector).order_by(MarketLoad.period.desc()).limit(1)
    ).first()
    metadata = (
        SourceMetadata.model_validate(source).model_dump()
        if source is not None
        else dict.fromkeys(SourceMetadata.model_fields)
    )
    return SeriesResponse(
        **metadata,
        sector=query.sector,
        marketer_code=marketer_code,
        community_code=query.community_code,
        series=points,
    )


def share_series(session: Session, marketer_code: str, query: ShareSeriesQuery) -> ShareSeriesResponse:
    selected = select(MarketLoad).where(MarketLoad.sector == query.sector)
    if query.start_period is not None:
        selected = selected.where(MarketLoad.period >= query.start_period)
    if query.end_period is not None:
        selected = selected.where(MarketLoad.period <= query.end_period)
    # Limit loads before joining facts, so no request aggregates more than 120 quarters.
    selected = selected.order_by(MarketLoad.period).limit(query.limit).offset(query.offset).subquery()
    load = aliased(MarketLoad, selected)
    join_conditions = [MarketRow.sector == load.sector, MarketRow.period == load.period]
    if query.community_code is not None:
        join_conditions.append(MarketRow.community_code == query.community_code)
    supplies = func.sum(
        case(
            (and_(MarketRow.category == "marketer", MarketRow.marketer_code == marketer_code), MarketRow.supplies),
            else_=0,
        )
    ).label("supplies")
    rows = session.execute(
        select(load, supplies, *_category_columns())
        .outerjoin(MarketRow, and_(*join_conditions))
        .group_by(*selected.c)
        .order_by(load.period)
    )
    points = []
    for row in rows:
        loaded, count, marketer_total, direct_total, unavailable_total = row
        points.append(
            ShareSeriesPoint(
                **RevisionMetadata.model_validate(loaded).model_dump(),
                period=loaded.period,
                package_name=loaded.package_name,
                resource_id=loaded.resource_id,
                supplies=count,
                marketer_supplies=marketer_total,
                direct_consumer_supplies=direct_total,
                unavailable_supplies=unavailable_total,
                share=count / marketer_total if marketer_total else None,
            )
        )
    return ShareSeriesResponse(
        sector=query.sector,
        marketer_code=marketer_code,
        community_code=query.community_code,
        denominator="supplies_with_registered_marketer",
        limit=query.limit,
        offset=query.offset,
        series=points,
    )


def community_shares(session: Session, marketer_code: str, query: QuarterQuery) -> CommunitySharesResponse:
    load = _load(session, query)
    rows = session.execute(
        select(
            MarketRow.community_code,
            func.sum(case((MarketRow.marketer_code == marketer_code, MarketRow.supplies), else_=0)).label("supplies"),
            *_category_columns(),
        )
        .where(MarketRow.sector == query.sector, MarketRow.period == query.period)
        .group_by(MarketRow.community_code)
        .order_by(MarketRow.community_code)
    ).mappings()
    return CommunitySharesResponse(
        **RevisionMetadata.model_validate(load).model_dump(),
        sector=query.sector,
        period=query.period,
        marketer_code=marketer_code,
        denominator="supplies_with_registered_marketer",
        items=[
            CommunityShare(
                **row, share=row["supplies"] / row["marketer_supplies"] if row["marketer_supplies"] else None
            )
            for row in rows
        ],
    )

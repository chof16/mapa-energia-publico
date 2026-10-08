"""Bounded ORM queries over imported market data, independent of HTTP routing."""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from electricity_map_api.market.exceptions import QuarterNotLoaded
from electricity_map_api.market.models import (
    MarketCompany,
    MarketCompanyName,
    MarketFact,
    MarketImport,
    MarketLoad,
    MarketPeriod,
    MarketSector,
)
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
    return func.coalesce(func.sum(case((MarketFact.category == category, MarketFact.supplies), else_=0)), 0)


def _sector_id(sector: str):
    return select(MarketSector.id).where(MarketSector.code == sector).scalar_subquery()


def _load_id(query: QuarterQuery):
    period = select(MarketPeriod.id).where(
        MarketPeriod.year == int(query.period[:4]), MarketPeriod.quarter == int(query.period[-1])
    )
    return (
        select(MarketImport.id)
        .where(MarketImport.sector_id == _sector_id(query.sector), MarketImport.period_id == period.scalar_subquery())
        .scalar_subquery()
    )


def _marketer_names(sector: str, marketer_code: str):
    return (
        select(MarketCompanyName.id)
        .join(MarketCompany, MarketCompany.id == MarketCompanyName.company_id)
        .where(
            MarketCompany.sector_id == _sector_id(sector),
            MarketCompany.role == "marketer",
            MarketCompany.code == marketer_code,
        )
    )


def _marketer_supplies(sector: str, marketer_code: str):
    return func.coalesce(
        func.sum(
            case(
                (MarketFact.marketer_name_id.in_(_marketer_names(sector, marketer_code)), MarketFact.supplies), else_=0
            )
        ),
        0,
    ).label("supplies")


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
    conditions = [MarketFact.load_id == _load_id(query)]
    if query.community_code is not None:
        conditions.append(MarketFact.community_code == query.community_code)
    totals = session.execute(select(*_category_columns()).where(*conditions)).mappings().one()
    # Join names only after reducing facts to one row per observed name.
    grouped = (
        select(MarketFact.marketer_name_id, func.sum(MarketFact.supplies).label("supplies"))
        .where(*conditions, MarketFact.category == "marketer")
        .group_by(MarketFact.marketer_name_id)
        .subquery()
    )
    supplies = func.sum(grouped.c.supplies).label("supplies")
    rows = session.execute(
        select(
            MarketCompany.code.label("marketer_code"), func.max(MarketCompanyName.name).label("observed_name"), supplies
        )
        .select_from(grouped)
        .join(MarketCompanyName, MarketCompanyName.id == grouped.c.marketer_name_id)
        .join(MarketCompany, MarketCompany.id == MarketCompanyName.company_id)
        .group_by(MarketCompany.code)
        .order_by(supplies.desc(), MarketCompany.code)
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
    conditions = [
        MarketImport.sector_id == _sector_id(query.sector),
        MarketFact.marketer_name_id.in_(_marketer_names(query.sector, marketer_code)),
    ]
    if query.community_code is not None:
        conditions.append(MarketFact.community_code == query.community_code)
    period = func.printf("%04dT%d", MarketPeriod.year, MarketPeriod.quarter)
    rows = session.execute(
        select(period.label("period"), func.sum(MarketFact.supplies).label("supplies"), MarketImport.metadata_modified)
        .select_from(MarketFact)
        .join(MarketImport, MarketImport.id == MarketFact.load_id)
        .join(MarketPeriod, MarketPeriod.id == MarketImport.period_id)
        .where(*conditions)
        .group_by(MarketImport.id, MarketPeriod.year, MarketPeriod.quarter, MarketImport.metadata_modified)
        .order_by(MarketPeriod.year, MarketPeriod.quarter)
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
    # Bound metadata first; never outer-join the denormalized fact view, which
    # SQLite materializes by scanning and joining every row in the database.
    loads = session.scalars(selected.order_by(MarketLoad.period).limit(query.limit).offset(query.offset)).all()
    totals = {}
    if loads:
        period = func.printf("%04dT%d", MarketPeriod.year, MarketPeriod.quarter)
        load_ids = dict(
            session.execute(
                select(period, MarketImport.id)
                .join(MarketPeriod, MarketPeriod.id == MarketImport.period_id)
                .where(MarketImport.sector_id == _sector_id(query.sector), period.in_([load.period for load in loads]))
            ).all()
        )
        conditions = [MarketFact.load_id.in_(list(load_ids.values()))]
        if query.community_code is not None:
            conditions.append(MarketFact.community_code == query.community_code)
        rows = session.execute(
            select(MarketFact.load_id, _marketer_supplies(query.sector, marketer_code), *_category_columns())
            .where(*conditions)
            .group_by(MarketFact.load_id)
        )
        by_id = {row[0]: row[1:] for row in rows}
        totals = {period: by_id.get(load_id, (0, 0, 0, 0)) for period, load_id in load_ids.items()}
    points = []
    for loaded in loads:
        count, marketer_total, direct_total, unavailable_total = totals[loaded.period]
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
            MarketFact.community_code,
            _marketer_supplies(query.sector, marketer_code),
            *_category_columns(),
        )
        .where(MarketFact.load_id == _load_id(query))
        .group_by(MarketFact.community_code)
        .order_by(MarketFact.community_code)
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

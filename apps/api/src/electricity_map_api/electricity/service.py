"""Bounded ORM queries over imported market data, independent of HTTP routing."""

from sqlalchemy import String, case, cast, func, select
from sqlalchemy.orm import Session

from electricity_map_api.electricity.exceptions import QuarterNotLoaded
from electricity_map_api.electricity.models import (
    ElectricityCompany,
    ElectricityCompanyName,
    ElectricityFact,
    ElectricityImport,
    ElectricityLoad,
    ElectricityPeriod,
    ElectricitySector,
)
from electricity_map_api.electricity.schemas import (
    CommunityShare,
    CommunitySharesResponse,
    MarketerShare,
    Quarter,
    QuarterQuery,
    QuartersResponse,
    SectorQuery,
    SeriesQuery,
    SeriesResponse,
    ShareSeriesPoint,
    ShareSeriesQuery,
    ShareSeriesResponse,
    SharesQuery,
    SharesResponse,
    SuppliesPoint,
)
from electricity_map_api.schemas import RevisionMetadata, SourceMetadata


def _load(session: Session, query: QuarterQuery) -> ElectricityLoad:
    load = session.get(ElectricityLoad, (query.sector, query.period))
    if load is None:
        raise QuarterNotLoaded
    return load


def _category_total(category: str):
    return func.coalesce(func.sum(case((ElectricityFact.category == category, ElectricityFact.supplies), else_=0)), 0)


def _sector_id(sector: str):
    return select(ElectricitySector.id).where(ElectricitySector.code == sector).scalar_subquery()


def _load_id(query: QuarterQuery):
    period = select(ElectricityPeriod.id).where(
        ElectricityPeriod.year == int(query.period[:4]), ElectricityPeriod.quarter == int(query.period[-1])
    )
    return (
        select(ElectricityImport.id)
        .where(
            ElectricityImport.sector_id == _sector_id(query.sector),
            ElectricityImport.period_id == period.scalar_subquery(),
        )
        .scalar_subquery()
    )


def _marketer_names(sector: str, marketer_code: str):
    return (
        select(ElectricityCompanyName.id)
        .join(ElectricityCompany, ElectricityCompany.id == ElectricityCompanyName.company_id)
        .where(
            ElectricityCompany.sector_id == _sector_id(sector),
            ElectricityCompany.role == "marketer",
            ElectricityCompany.code == marketer_code,
        )
    )


def _marketer_supplies(sector: str, marketer_code: str):
    return func.coalesce(
        func.sum(
            case(
                (
                    ElectricityFact.marketer_name_id.in_(_marketer_names(sector, marketer_code)),
                    ElectricityFact.supplies,
                ),
                else_=0,
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
        select(ElectricityLoad)
        .where(ElectricityLoad.sector == query.sector)
        .order_by(ElectricityLoad.period.desc())
        .limit(120)
    )
    return QuartersResponse(sector=query.sector, quarters=[Quarter.model_validate(load) for load in loads])


def shares(session: Session, query: SharesQuery) -> SharesResponse:
    load = _load(session, query)
    conditions = [ElectricityFact.load_id == _load_id(query)]
    if query.community_code is not None:
        conditions.append(ElectricityFact.community_code == query.community_code)
    totals = session.execute(select(*_category_columns()).where(*conditions)).mappings().one()
    # Join names only after reducing facts to one row per observed name.
    grouped = (
        select(ElectricityFact.marketer_name_id, func.sum(ElectricityFact.supplies).label("supplies"))
        .where(*conditions, ElectricityFact.category == "marketer")
        .group_by(ElectricityFact.marketer_name_id)
        .subquery()
    )
    supplies = func.sum(grouped.c.supplies).label("supplies")
    rows = session.execute(
        select(
            ElectricityCompany.code.label("marketer_code"),
            func.max(ElectricityCompanyName.name).label("observed_name"),
            supplies,
        )
        .select_from(grouped)
        .join(ElectricityCompanyName, ElectricityCompanyName.id == grouped.c.marketer_name_id)
        .join(ElectricityCompany, ElectricityCompany.id == ElectricityCompanyName.company_id)
        .group_by(ElectricityCompany.code)
        .order_by(supplies.desc(), ElectricityCompany.code)
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
        ElectricityImport.sector_id == _sector_id(query.sector),
        ElectricityFact.marketer_name_id.in_(_marketer_names(query.sector, marketer_code)),
    ]
    if query.community_code is not None:
        conditions.append(ElectricityFact.community_code == query.community_code)
    period = cast(ElectricityPeriod.year, String) + "T" + cast(ElectricityPeriod.quarter, String)
    rows = session.execute(
        select(
            period.label("period"),
            func.sum(ElectricityFact.supplies).label("supplies"),
            ElectricityImport.metadata_modified,
        )
        .select_from(ElectricityFact)
        .join(ElectricityImport, ElectricityImport.id == ElectricityFact.load_id)
        .join(ElectricityPeriod, ElectricityPeriod.id == ElectricityImport.period_id)
        .where(*conditions)
        .group_by(
            ElectricityImport.id, ElectricityPeriod.year, ElectricityPeriod.quarter, ElectricityImport.metadata_modified
        )
        .order_by(ElectricityPeriod.year, ElectricityPeriod.quarter)
        .limit(120)
    ).mappings()
    points = [SuppliesPoint.model_validate(row) for row in rows]
    source = session.scalars(
        select(ElectricityLoad)
        .where(ElectricityLoad.sector == query.sector)
        .order_by(ElectricityLoad.period.desc())
        .limit(1)
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
    selected = select(ElectricityLoad).where(ElectricityLoad.sector == query.sector)
    if query.start_period is not None:
        selected = selected.where(ElectricityLoad.period >= query.start_period)
    if query.end_period is not None:
        selected = selected.where(ElectricityLoad.period <= query.end_period)
    # Bound metadata first; never outer-join the denormalized fact view, which
    # SQLite materializes by scanning and joining every row in the database.
    loads = session.scalars(selected.order_by(ElectricityLoad.period).limit(query.limit).offset(query.offset)).all()
    totals = {}
    if loads:
        period = cast(ElectricityPeriod.year, String) + "T" + cast(ElectricityPeriod.quarter, String)
        load_ids = dict(
            session.execute(
                select(period, ElectricityImport.id)
                .join(ElectricityPeriod, ElectricityPeriod.id == ElectricityImport.period_id)
                .where(
                    ElectricityImport.sector_id == _sector_id(query.sector), period.in_([load.period for load in loads])
                )
            ).all()
        )
        conditions = [ElectricityFact.load_id.in_(list(load_ids.values()))]
        if query.community_code is not None:
            conditions.append(ElectricityFact.community_code == query.community_code)
        rows = session.execute(
            select(ElectricityFact.load_id, _marketer_supplies(query.sector, marketer_code), *_category_columns())
            .where(*conditions)
            .group_by(ElectricityFact.load_id)
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
            ElectricityFact.community_code,
            _marketer_supplies(query.sector, marketer_code),
            *_category_columns(),
        )
        .where(ElectricityFact.load_id == _load_id(query))
        .group_by(ElectricityFact.community_code)
        .order_by(ElectricityFact.community_code)
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

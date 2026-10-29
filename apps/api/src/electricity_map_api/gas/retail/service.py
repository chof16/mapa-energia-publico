"""Bounded, load-scoped reads; no inference of identities or unreviewed values."""

import json
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import and_, case, func, inspect, or_, select, union_all
from sqlalchemy.orm import Session

from electricity_map_api.gas.retail import schemas as dto
from electricity_map_api.gas.retail.exceptions import (
    GasRetailEvidenceLimit,
    GasRetailMarketerNotFound,
    GasRetailNotLoaded,
)
from electricity_map_api.gas.retail.models import (
    GasRetailAudit as Audit,
)
from electricity_map_api.gas.retail.models import (
    GasRetailCatalogue as Catalogue,
)
from electricity_map_api.gas.retail.models import (
    GasRetailEntity as Entity,
)
from electricity_map_api.gas.retail.models import (
    GasRetailLoad as Load,
)
from electricity_map_api.gas.retail.models import (
    GasRetailMapping as Mapping,
)
from electricity_map_api.gas.retail.models import (
    GasRetailObservation as Observation,
)
from electricity_map_api.gas.retail.models import GasRetailObservationDetail as Detail
from electricity_map_api.gas.retail.models import (
    GasRetailQuarter as Quarter,
)
from electricity_map_api.gas.retail.models import (
    GasRetailSource as Source,
)
from electricity_map_api.gas.retail.models import GasRetailSourceAudit as SourceAudit
from electricity_map_api.gas.retail.models import GasRetailUnresolvedObservation as Unresolved


def _bounded(session: Session, statement, maximum: int):
    rows = session.scalars(statement.limit(maximum + 1)).all()
    if len(rows) > maximum:
        raise GasRetailEvidenceLimit
    return rows


def _array(value: str, maximum: int) -> list:
    # These are importer-owned JSON arrays, never client-supplied decoder input.
    if len(value) > 50_000:
        raise GasRetailEvidenceLimit
    result = json.loads(value)
    if not isinstance(result, list) or len(result) > maximum:
        raise GasRetailEvidenceLimit
    return result


def _revision(session: Session, load_id: str | None) -> dto.GasRetailRevision:
    statement = select(Load)
    if load_id:
        statement = statement.where(Load.load_id == load_id)
    row = session.scalar(statement.order_by(Load.imported_at.desc(), Load.load_id).limit(1))
    if row is None:
        raise GasRetailNotLoaded
    return dto.GasRetailRevision.model_validate(row)


def _sources(session: Session, load_id: str) -> dict[str, dto.GasRetailSourceMetadata]:
    return {
        row.source_id: dto.GasRetailSourceMetadata.model_validate(row)
        for row in _bounded(session, select(Source).where(Source.load_id == load_id), 200)
    }


def _audit(row: Audit, sources: dict) -> dto.GasRetailAuditMetadata:
    return dto.GasRetailAuditMetadata(
        period=row.period,
        metric=row.metric,
        status=row.status,
        pages=_array(row.pages_json, 200),
        sources=[sources[source_id] for source_id in _array(row.source_ids_json, 10)],
        note=row.note,
    )


def _source_reviews(session: Session, load_id: str, sources: dict) -> dict:
    # Introspection preserves v1 databases without installing anything at startup.
    if not inspect(session.connection()).has_table(SourceAudit.__tablename__):
        return {}
    rows = _bounded(session, select(SourceAudit).where(SourceAudit.load_id == load_id), 2000)
    return {
        (row.period, row.metric, row.source_id): dto.GasRetailSourceAuditMetadata(
            source=sources[row.source_id],
            period=row.period,
            metric=row.metric,
            status=row.status,
            table_review_status=row.table_review_status,
            retailer_coverage=row.retailer_coverage,
            geographic_scope=row.geographic_scope,
            pages=_array(row.pages_json, 200),
            note=row.note,
        )
        for row in rows
    }


def _identity_status(note: str) -> str:
    # The v2 importer stores this explicit Work decision as a prefix, not a name heuristic.
    status = note.partition(":")[0]
    return status if status in {"source_local_identity", "reviewed_identity"} else "legacy_unspecified"


def _approved_source():
    return and_(
        SourceAudit.status == "reviewed",
        SourceAudit.table_review_status == "reviewed",
        SourceAudit.retailer_coverage == "reviewed",
    )


def _source_join(period, metric, source_id, load_id):
    return and_(
        SourceAudit.load_id == load_id,
        SourceAudit.source_id == source_id,
        SourceAudit.period == period,
        SourceAudit.metric == metric,
    )


def _reviewed_quarters(load_id: str, extended: bool = False):
    if extended:
        return (
            select(Quarter)
            .join(SourceAudit, _source_join(Quarter.period, Quarter.metric, Quarter.source_id, Quarter.load_id))
            .where(
                Quarter.load_id == load_id,
                or_(
                    _approved_source(),
                    and_(SourceAudit.status == "source_error", SourceAudit.table_review_status == "source_error"),
                ),
            )
        )
    return (
        select(Quarter)
        .join(
            Audit,
            (Audit.load_id == Quarter.load_id) & (Audit.period == Quarter.period) & (Audit.metric == Quarter.metric),
        )
        .where(Quarter.load_id == load_id, Audit.status == "reviewed")
    )


def periods(session: Session, query: dto.GasRetailPeriodQuery) -> dto.GasRetailPeriodsResponse:
    revision = _revision(session, query.load_id)
    sources = _sources(session, revision.load_id)
    source_reviews = _source_reviews(session, revision.load_id, sources)
    filters = [Audit.load_id == revision.load_id, Audit.metric == query.metric]
    if query.period:
        filters.append(Audit.period == query.period)
    total = session.scalar(select(func.count()).select_from(Audit).where(*filters))
    audits = session.scalars(
        select(Audit).where(*filters).order_by(Audit.period).limit(query.limit).offset(query.offset)
    ).all()
    eligible, cells = _reviewed_mappings(revision.load_id, bool(source_reviews))
    company_periods = eligible.where(
        cells.c.metric == query.metric,
        cells.c.scope == query.scope,
        cells.c.period.in_([row.period for row in audits]),
    )
    if source_reviews:
        company_periods = company_periods.where(_approved_source(), Detail.review_status == "reviewed")
    company_periods = company_periods.with_only_columns(Mapping.gas_id, cells.c.period).subquery()
    counts = dict(
        session.execute(
            select(company_periods.c.period, func.count(func.distinct(company_periods.c.gas_id)))
            .group_by(company_periods.c.period)
            .limit(100)
        ).all()
    )
    return dto.GasRetailPeriodsResponse(
        revision=revision,
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=[
            dto.GasRetailPeriodItem(
                audit=_audit(row, sources),
                scope=query.scope,
                reviewed_retailer_count=counts.get(row.period, 0),
                source_audits=[
                    review
                    for (period, metric, _), review in sorted(source_reviews.items())
                    if period == row.period and metric == row.metric
                ],
            )
            for row in audits
        ],
    )


def _reviewed_mappings(load_id: str, extended: bool = False):
    month = func.substr(Observation.month, 6, 2)
    period = (
        func.substr(Observation.month, 1, 4)
        + "T"
        + case((month <= "03", "1"), (month <= "06", "2"), (month <= "09", "3"), else_="4")
    )
    columns = ("load_id", "mapping_id", "source_id", "observation_id", "metric", "scope", "status")
    dated = select(*(getattr(Observation, name) for name in columns), period.label("period")).where(
        Observation.load_id == load_id
    )
    cells = (
        union_all(
            dated,
            select(*(getattr(Unresolved, name) for name in columns), Unresolved.period).where(
                Unresolved.load_id == load_id
            ),
        )
        if extended
        else dated
    ).subquery()
    statement = (
        select(Mapping)
        .join(Entity, (Entity.load_id == Mapping.load_id) & (Entity.gas_id == Mapping.gas_id))
        .join(cells, (cells.c.load_id == Mapping.load_id) & (cells.c.mapping_id == Mapping.mapping_id))
        .join(
            Audit,
            (Audit.load_id == cells.c.load_id) & (Audit.period == cells.c.period) & (Audit.metric == cells.c.metric),
        )
        .where(Mapping.load_id == load_id, Entity.kind == "retailer")
        .distinct()
    )
    if extended:
        statement = (
            # Source-local IDs describe evidence, not public company identities.
            # The importer owns canonical continuity; never infer it from labels.
            statement.where(Entity.review_note.startswith("reviewed_identity:", autoescape=True))
            .join(SourceAudit, _source_join(cells.c.period, cells.c.metric, cells.c.source_id, cells.c.load_id))
            .join(Detail, (Detail.load_id == cells.c.load_id) & (Detail.observation_id == cells.c.observation_id))
            .where(
                or_(
                    and_(_approved_source(), Detail.review_status == "reviewed"),
                    and_(
                        or_(
                            _approved_source(),
                            and_(
                                SourceAudit.status == "source_error", SourceAudit.table_review_status == "source_error"
                            ),
                        ),
                        Detail.review_status == "source_error",
                    ),
                )
            )
        )
    else:
        statement = statement.where(Audit.status == "reviewed")
    return statement, cells


def marketers(session: Session, query: dto.GasRetailMarketersQuery) -> dto.GasRetailMarketersResponse:
    revision = _revision(session, query.load_id)
    sources = _sources(session, revision.load_id)
    source_reviews = _source_reviews(session, revision.load_id, sources)
    statement, cells = _reviewed_mappings(revision.load_id, bool(source_reviews))
    statement = statement.where(cells.c.metric == query.metric, cells.c.scope == query.scope)
    if query.period:
        statement = statement.where(Audit.period == query.period)
    # Rank eligible observations before search: an older alias must not change
    # the representative source or produce another entry for the same company.
    candidates = statement.with_only_columns(
        Mapping.load_id, Mapping.mapping_id, Mapping.gas_id, Audit.period
    ).subquery()
    ranked = select(
        candidates.c.load_id,
        candidates.c.mapping_id,
        func.row_number()
        .over(
            partition_by=(candidates.c.load_id, candidates.c.gas_id),
            order_by=(candidates.c.period.desc(), candidates.c.mapping_id),
        )
        .label("company_rank"),
    ).subquery()
    companies = (
        select(Mapping, Entity)
        .join(
            ranked,
            (ranked.c.load_id == Mapping.load_id)
            & (ranked.c.mapping_id == Mapping.mapping_id)
            & (ranked.c.company_rank == 1),
        )
        .join(Entity, (Entity.load_id == Mapping.load_id) & (Entity.gas_id == Mapping.gas_id))
        .where(Mapping.load_id == revision.load_id)
    )
    if query.search:
        # Reviewed historical aliases identify the eligible company even when
        # its current-period name, metric or scope differs. Partial aliases stay private.
        matching_statement, _ = _reviewed_mappings(revision.load_id, bool(source_reviews))
        matching_ids = matching_statement.where(
            Mapping.observed_name.icontains(query.search, autoescape=True)
        ).with_only_columns(Mapping.gas_id)
        companies = companies.where(
            Entity.name.icontains(query.search, autoescape=True) | Mapping.gas_id.in_(matching_ids)
        )
    total = session.scalar(select(func.count()).select_from(companies.subquery()))
    rows = session.execute(
        companies.order_by(func.lower(Entity.name), Mapping.gas_id).limit(query.limit).offset(query.offset)
    )
    return dto.GasRetailMarketersResponse(
        revision=revision,
        metric=query.metric,
        scope=query.scope,
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=[
            dto.GasRetailMarketer(
                marketer_id=row.gas_id,
                company_name=entity.name,
                observed_name=row.observed_name,
                source=sources[row.source_id],
                mapping_review_note=row.review_note,
                identity_review_note=entity.review_note,
                identity_status=_identity_status(entity.review_note),
            )
            for row, entity in rows
        ],
    )


def _value(session: Session, row: Quarter, sources: dict, source_reviews: dict) -> dto.GasRetailValue:
    ids = _array(row.observation_ids_json, 100)
    observations = session.execute(
        select(Observation, Mapping)
        .join(Mapping, (Mapping.load_id == Observation.load_id) & (Mapping.mapping_id == Observation.mapping_id))
        .where(
            Observation.load_id == row.load_id,
            Observation.source_id == row.source_id,
            Observation.observation_id.in_(ids),
            Mapping.gas_id == row.gas_id,
            Observation.metric == row.metric,
            Observation.scope == row.scope,
            Observation.unit == row.unit,
        )
        .order_by(Observation.month, Observation.observation_id)
        .limit(101)
    ).all()
    unresolved = []
    details = {}
    source_audit = source_reviews.get((row.period, row.metric, row.source_id))
    if source_reviews:
        unresolved = session.execute(
            select(Unresolved, Mapping)
            .join(Mapping, (Mapping.load_id == Unresolved.load_id) & (Mapping.mapping_id == Unresolved.mapping_id))
            .where(
                Unresolved.load_id == row.load_id,
                Unresolved.source_id == row.source_id,
                Unresolved.observation_id.in_(ids),
                Mapping.gas_id == row.gas_id,
                Unresolved.period == row.period,
                Unresolved.metric == row.metric,
                Unresolved.scope == row.scope,
                Unresolved.unit == row.unit,
            )
            .order_by(Unresolved.observation_id)
            .limit(101)
        ).all()
        details = {
            detail.observation_id: detail
            for detail in _bounded(
                session, select(Detail).where(Detail.load_id == row.load_id, Detail.observation_id.in_(ids)), 100
            )
        }
        if set(details) != set(ids) or source_audit is None:
            raise GasRetailEvidenceLimit
    if len(observations) + len(unresolved) != len(ids):
        raise GasRetailEvidenceLimit
    source_approved = source_audit is None or (
        source_audit.status == "reviewed"
        and source_audit.table_review_status == "reviewed"
        and source_audit.retailer_coverage == "reviewed"
    )
    review_status = "reviewed"
    if not source_approved or unresolved or any(detail.review_status == "source_error" for detail in details.values()):
        review_status = "source_error"
    if any(detail.review_status == "partial" for detail in details.values()):
        review_status = "partial"
    approved = review_status == "reviewed"
    status = row.status
    if not approved:
        status = (
            "missing"
            if review_status == "partial"
            else row.status
            if row.status in {"missing", "source_error"}
            else "source_error"
        )
    monthly = []
    unresolved_cells = []
    withheld = []
    fields = (
        "observation_id",
        "mapping_id",
        "metric",
        "scope",
        "unit",
        "page",
        "table_label",
        "source_row",
        "raw_value",
        "status",
        "review_note",
    )
    for observation, mapping in [*observations, *unresolved]:
        detail = details.get(observation.observation_id)
        cell_review = detail.review_status if detail else "reviewed"
        if cell_review == "partial":
            withheld.append(observation.observation_id)
            continue
        common = {name: getattr(observation, name) for name in fields}
        common.update(
            observed_name=mapping.observed_name,
            mapping_review_note=mapping.review_note,
            original_unit=detail.original_unit if detail else observation.unit,
            review_status=cell_review,
        )
        if isinstance(observation, Unresolved):
            unresolved_cells.append(dto.GasRetailUnresolvedCell(**common, period=observation.period))
        else:
            cell_approved = source_approved and cell_review == "reviewed"
            monthly.append(
                dto.GasRetailMonthlyObservation(
                    **common,
                    month=observation.month,
                    value=observation.value if cell_approved else None,
                    upper_bound=observation.upper_bound if cell_approved else None,
                    publication_status="reviewed" if cell_approved else "source_error",
                )
            )
    factor = {"clients": Decimal(1), "MWh": Decimal(1), "GWh": Decimal(1000), "kWh": Decimal("0.001")}[row.unit]
    return dto.GasRetailValue(
        gas_id=row.gas_id,
        source=sources[row.source_id],
        period=row.period,
        metric=row.metric,
        scope=row.scope,
        status=status,
        unit="clients" if row.metric == "clients" else "MWh",
        value=Decimal(row.value) * factor if approved and row.value is not None else None,
        upper_bound=Decimal(row.upper_bound) * factor if approved and row.upper_bound is not None else None,
        original_unit=row.unit,
        original_value=row.value if approved else None,
        original_upper_bound=row.upper_bound if approved else None,
        missing_months=_array(row.missing_months_json, 3),
        input_statuses=_array(row.input_statuses_json, 100),
        observations=monthly,
        source_audit=source_audit,
        review_status=review_status,
        withheld_observation_ids=withheld,
        unresolved_observations=unresolved_cells,
    )


def _series_value(
    session: Session, row: Quarter, totals: list[Quarter], sources: dict, source_reviews: dict
) -> dto.GasRetailSeriesValue:
    value = _value(session, row, sources, source_reviews)
    candidates = [total for total in totals if total.source_id == row.source_id and total.period == row.period]
    denominator = _value(session, candidates[0], sources, source_reviews) if len(candidates) == 1 else None
    share = None
    status = "ambiguous" if len(candidates) > 1 else "missing"
    if denominator is not None:
        status = "unavailable"
        if denominator.status in {"exact", "zero"}:
            status = "zero" if denominator.value == 0 else "matched"
            if denominator.value and value.status in {"exact", "zero"}:
                if value.value <= denominator.value:
                    share = value.value / denominator.value
                else:
                    status = "inconsistent"
    return dto.GasRetailSeriesValue(
        **value.model_dump(), denominator=denominator, denominator_status=status, share=share
    )


def series(session: Session, marketer_id: str, query: dto.GasRetailSeriesQuery) -> dto.GasRetailSeriesResponse:
    revision = _revision(session, query.load_id)
    sources = _sources(session, revision.load_id)
    source_reviews = _source_reviews(session, revision.load_id, sources)
    mappings, _ = _reviewed_mappings(revision.load_id, bool(source_reviews))
    if session.scalar(mappings.where(Mapping.gas_id == marketer_id).limit(1)) is None:
        raise GasRetailMarketerNotFound
    entity = session.scalar(
        select(Entity).where(Entity.load_id == revision.load_id, Entity.gas_id == marketer_id).limit(1)
    )
    filters = [Audit.load_id == revision.load_id, Audit.metric == query.metric]
    if query.start_period:
        filters.append(Audit.period >= query.start_period)
    if query.end_period:
        filters.append(Audit.period <= query.end_period)
    total = session.scalar(select(func.count()).select_from(Audit).where(*filters))
    audits = session.scalars(
        select(Audit).where(*filters).order_by(Audit.period).limit(query.limit).offset(query.offset)
    ).all()
    reviewed = [row.period for row in audits if source_reviews or row.status == "reviewed"]
    statement = _reviewed_quarters(revision.load_id, bool(source_reviews)).where(
        Quarter.period.in_(reviewed), Quarter.metric == query.metric, Quarter.scope == query.scope
    )
    rows = _bounded(
        session,
        statement.where(Quarter.gas_id == marketer_id).order_by(Quarter.period, Quarter.source_id, Quarter.unit),
        1000,
    )
    totals = _bounded(
        session,
        statement.join(Entity, (Entity.load_id == Quarter.load_id) & (Entity.gas_id == Quarter.gas_id)).where(
            Entity.kind == "total", Quarter.source_id.in_({row.source_id for row in rows})
        ),
        1000,
    )
    by_period = defaultdict(list)
    for row in rows:
        by_period[row.period].append(_series_value(session, row, totals, sources, source_reviews))
    return dto.GasRetailSeriesResponse(
        revision=revision,
        marketer_id=marketer_id,
        company_name=entity.name,
        identity_review_note=entity.review_note,
        identity_status=_identity_status(entity.review_note),
        metric=query.metric,
        scope=query.scope,
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=[
            dto.GasRetailSeriesPoint(
                audit=_audit(row, sources),
                availability="reviewed"
                if any(value.review_status == "reviewed" for value in by_period[row.period])
                else (
                    "unreviewed"
                    if any(value.review_status == "partial" for value in by_period[row.period])
                    or (not by_period[row.period] and row.status in {"partial", "located", "not_reviewed"})
                    else "unavailable"
                ),
                records=by_period[row.period],
                source_audits=[
                    review
                    for (period, metric, _), review in sorted(source_reviews.items())
                    if period == row.period and metric == row.metric
                ],
            )
            for row in audits
        ],
    )


def revisions(session: Session, query: dto.GasRetailPageQuery) -> dto.GasRetailRevisionsResponse:
    filters = [Load.load_id == query.load_id] if query.load_id else []
    total = session.scalar(select(func.count()).select_from(Load).where(*filters))
    rows = session.scalars(
        select(Load)
        .where(*filters)
        .order_by(Load.imported_at.desc(), Load.load_id)
        .limit(query.limit)
        .offset(query.offset)
    ).all()
    load_ids = [row.load_id for row in rows]
    counts = session.execute(
        select(Audit.load_id, Audit.metric, Audit.status, func.count())
        .where(Audit.load_id.in_(load_ids))
        .group_by(Audit.load_id, Audit.metric, Audit.status)
        .order_by(Audit.load_id, Audit.metric, Audit.status)
        .limit(1201)
    ).all()
    if len(counts) > 1200:
        raise GasRetailEvidenceLimit
    ranked = (
        select(
            Audit.load_id,
            Audit.period,
            Audit.metric,
            func.row_number()
            .over(partition_by=Audit.load_id, order_by=(Audit.period, Audit.metric))
            .label("issue_rank"),
        )
        .where(Audit.load_id.in_(load_ids), Audit.status != "reviewed")
        .subquery()
    )
    issues = _bounded(
        session,
        select(Audit)
        .join(
            ranked,
            (ranked.c.load_id == Audit.load_id) & (ranked.c.period == Audit.period) & (ranked.c.metric == Audit.metric),
        )
        .where(ranked.c.issue_rank <= 10)
        .order_by(Audit.load_id, Audit.period, Audit.metric),
        1000,
    )
    items = []
    for row in rows:
        issue_count = sum(
            count for load_id, _, status, count in counts if load_id == row.load_id and status != "reviewed"
        )
        audit_url = f"/v1/gas/retail/periods?load_id={row.load_id}"
        selected_issues = [issue for issue in issues if issue.load_id == row.load_id]
        items.append(
            dto.GasRetailRevisionCoverage(
                **dto.GasRetailRevision.model_validate(row).model_dump(),
                coverage=[
                    dto.GasRetailMetricCoverage(
                        metric=metric,
                        counts=[
                            dto.GasRetailAuditCount(status=status, periods=count)
                            for load_id, observed_metric, status, count in counts
                            if load_id == row.load_id and observed_metric == metric
                        ],
                        audits_url=f"{audit_url}&metric={metric}",
                    )
                    for metric in ("clients", "sales")
                ],
                issue_count=issue_count,
                issues_truncated=issue_count > len(selected_issues),
                issues=[
                    dto.GasRetailCoverageIssue(
                        period=issue.period,
                        metric=issue.metric,
                        status=issue.status,
                        note=issue.note,
                        audit_url=f"{audit_url}&metric={issue.metric}&period={issue.period}",
                    )
                    for issue in selected_issues
                ],
            )
        )
    return dto.GasRetailRevisionsResponse(
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=items,
    )


def reference_marketers(session: Session, query: dto.GasRetailPageQuery) -> dto.GasReferenceMarketersResponse:
    revision = _revision(session, query.load_id)
    sources = _sources(session, revision.load_id)
    statement = select(Catalogue.gas_id).where(Catalogue.load_id == revision.load_id).distinct()
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    ids = session.scalars(statement.order_by(Catalogue.gas_id).limit(query.limit).offset(query.offset)).all()
    rows = _bounded(
        session,
        select(Catalogue)
        .where(Catalogue.load_id == revision.load_id, Catalogue.gas_id.in_(ids))
        .order_by(Catalogue.gas_id, Catalogue.evidence_on, Catalogue.source_id),
        100,
    )
    return dto.GasReferenceMarketersResponse(
        revision=revision,
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=[
            dto.GasReferenceMarketer(
                marketer_id=gas_id,
                observations=[
                    dto.GasReferenceObservation(
                        observed_name=row.observed_name,
                        designation=row.designation,
                        evidence_on=row.evidence_on,
                        page=row.page,
                        review_note=row.review_note,
                        source=sources[row.source_id],
                    )
                    for row in rows
                    if row.gas_id == gas_id
                ],
            )
            for gas_id in ids
        ],
    )

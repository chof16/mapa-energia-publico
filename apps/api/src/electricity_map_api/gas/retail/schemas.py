"""Independent gas DTOs; numeric availability never substitutes for table review."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from electricity_map_api.schemas import Count, PageLimit, PageOffset, PageQuery, QueryDTO, ResponseDTO

GasRetailId = Annotated[str, Field(pattern=r"^gas-[a-z0-9-]{1,75}$")]
GasRetailHash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
GasRetailPeriod = Annotated[str, Field(pattern=r"^20[0-9]{2}T[1-4]$")]
GasRetailMetric = Literal["clients", "sales"]
GasRetailScope = Literal["whole_market", "liberalised", "regulated"]
GasRetailStatus = Literal["exact", "zero", "missing", "suppressed", "source_error", "bounded"]
GasRetailAuditStatus = Literal["not_reviewed", "located", "partial", "reviewed", "unavailable", "source_error"]
GasRetailUnit = Literal["clients", "MWh", "GWh", "kWh"]
GasRetailDecimal = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
GasRetailSeriesLimit = Annotated[int, Field(ge=1, le=120)]
GasRetailCellReview = Literal["reviewed", "partial", "source_error"]
GasRetailIdentityStatus = Literal["reviewed_identity", "source_local_identity", "legacy_unspecified"]


class GasRetailPageQuery(PageQuery):
    load_id: GasRetailHash | None = None


class GasRetailPeriodQuery(GasRetailPageQuery):
    metric: GasRetailMetric = "clients"
    scope: GasRetailScope = "whole_market"
    period: GasRetailPeriod | None = None


class GasRetailMarketersQuery(GasRetailPeriodQuery):
    search: Annotated[str, Field(min_length=1, max_length=100)] | None = None


class GasRetailSeriesQuery(QueryDTO):
    load_id: GasRetailHash | None = None
    metric: GasRetailMetric = "clients"
    scope: GasRetailScope = "whole_market"
    start_period: GasRetailPeriod | None = None
    end_period: GasRetailPeriod | None = None
    limit: GasRetailSeriesLimit = 120
    offset: PageOffset = 0

    @model_validator(mode="after")
    def ordered_periods(self):
        if self.start_period and self.end_period and self.start_period > self.end_period:
            raise ValueError("start_period must not follow end_period")
        return self


class GasRetailRevision(ResponseDTO):
    load_id: GasRetailHash
    reviewed_on: str
    imported_at: str
    complete: Literal[False] = False
    reuse_status: Literal["review_pending"]


class GasRetailSourceMetadata(ResponseDTO):
    source_id: str
    url: str
    title: str
    publisher: str
    published_on: str | None
    retrieved_on: str
    sha256: GasRetailHash
    media_type: Literal["pdf", "html"]
    page_count: Annotated[int, Field(ge=0, le=200)]
    reuse_status: Literal["review_pending"]
    notes: str


class GasRetailAuditMetadata(ResponseDTO):
    period: GasRetailPeriod
    metric: GasRetailMetric
    status: GasRetailAuditStatus
    pages: list[int] = Field(max_length=200)
    sources: list[GasRetailSourceMetadata] = Field(max_length=10)
    note: str


class GasRetailSourceAuditMetadata(ResponseDTO):
    source: GasRetailSourceMetadata
    period: GasRetailPeriod
    metric: GasRetailMetric
    status: GasRetailAuditStatus
    table_review_status: Literal["reviewed", "partial", "unavailable", "not_reviewed", "source_error"]
    retailer_coverage: Literal["reviewed", "partial", "unknown", "unavailable_in_table"]
    geographic_scope: str
    pages: list[int] = Field(max_length=200)
    note: str


class GasRetailContext(ResponseDTO):
    sector: Literal["gas"] = "gas"
    complete: Literal[False] = False
    revision: GasRetailRevision
    geographic_scope: Literal["source_defined"] = "source_defined"
    geographic_note: str = (
        "El ámbito geográfico depende de cada fuente; no se presupone comparabilidad nacional histórica."
    )
    identity_note: str = (
        "Identificadores propios de gas; continuidad solo mediante correspondencias revisadas, sin equivalencia R2."
    )


class GasRetailPage(GasRetailContext):
    total: Count
    limit: PageLimit
    offset: PageOffset


class GasRetailPeriodItem(ResponseDTO):
    audit: GasRetailAuditMetadata
    scope: GasRetailScope
    reviewed_retailer_count: Count
    source_audits: list[GasRetailSourceAuditMetadata] = Field(default_factory=list, max_length=10)


class GasRetailPeriodsResponse(GasRetailPage):
    items: list[GasRetailPeriodItem] = Field(max_length=100)


class GasRetailMarketer(ResponseDTO):
    marketer_id: GasRetailId
    company_name: str
    observed_name: str
    source: GasRetailSourceMetadata
    mapping_review_note: str
    identity_review_note: str = ""
    identity_status: GasRetailIdentityStatus = "legacy_unspecified"


class GasRetailMarketersResponse(GasRetailPage):
    metric: GasRetailMetric
    scope: GasRetailScope
    items: list[GasRetailMarketer] = Field(max_length=100)


class GasRetailMonthlyObservation(ResponseDTO):
    observation_id: str
    mapping_id: str
    observed_name: str
    mapping_review_note: str
    month: str
    metric: GasRetailMetric
    scope: GasRetailScope
    unit: GasRetailUnit
    page: Annotated[int, Field(ge=1, le=200)]
    table_label: str
    source_row: str
    raw_value: str
    status: GasRetailStatus
    value: GasRetailDecimal | None
    upper_bound: GasRetailDecimal | None
    upper_bound_exclusive: Literal[True] = True
    review_note: str
    original_unit: str
    review_status: GasRetailCellReview
    publication_status: Literal["reviewed", "source_error"]


class GasRetailUnresolvedCell(ResponseDTO):
    observation_id: str
    mapping_id: str
    observed_name: str
    mapping_review_note: str
    period: GasRetailPeriod
    month: None = None
    metric: GasRetailMetric
    scope: GasRetailScope
    unit: GasRetailUnit
    original_unit: str
    page: Annotated[int, Field(ge=1, le=200)]
    table_label: str
    source_row: str
    raw_value: str
    status: Literal["source_error"] = "source_error"
    value: None = None
    upper_bound: None = None
    review_status: GasRetailCellReview
    review_note: str


class GasRetailValue(ResponseDTO):
    gas_id: GasRetailId
    source: GasRetailSourceMetadata
    period: GasRetailPeriod
    metric: GasRetailMetric
    scope: GasRetailScope
    status: GasRetailStatus
    unit: Literal["clients", "MWh"]
    value: GasRetailDecimal | None
    upper_bound: GasRetailDecimal | None
    upper_bound_exclusive: Literal[True] = True
    original_unit: GasRetailUnit
    original_value: GasRetailDecimal | None
    original_upper_bound: GasRetailDecimal | None
    missing_months: list[str] = Field(max_length=3)
    input_statuses: list[GasRetailStatus] = Field(max_length=100)
    observations: list[GasRetailMonthlyObservation] = Field(max_length=100)
    source_audit: GasRetailSourceAuditMetadata | None = None
    review_status: GasRetailCellReview = "reviewed"
    withheld_observation_ids: list[str] = Field(default_factory=list, max_length=100)
    unresolved_observations: list[GasRetailUnresolvedCell] = Field(default_factory=list, max_length=100)


class GasRetailSeriesValue(GasRetailValue):
    denominator: GasRetailValue | None
    denominator_status: Literal["matched", "missing", "ambiguous", "unavailable", "zero", "inconsistent"]
    share: Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)] | None


class GasRetailSeriesPoint(ResponseDTO):
    audit: GasRetailAuditMetadata
    availability: Literal["reviewed", "unreviewed", "unavailable"]
    records: list[GasRetailSeriesValue] = Field(max_length=100)
    source_audits: list[GasRetailSourceAuditMetadata] = Field(default_factory=list, max_length=10)


class GasRetailSeriesResponse(GasRetailContext):
    marketer_id: GasRetailId
    company_name: str
    identity_review_note: str = ""
    identity_status: GasRetailIdentityStatus = "legacy_unspecified"
    metric: GasRetailMetric
    scope: GasRetailScope
    total: Count
    limit: GasRetailSeriesLimit
    offset: PageOffset
    items: list[GasRetailSeriesPoint] = Field(max_length=120)


class GasRetailAuditCount(ResponseDTO):
    status: GasRetailAuditStatus
    periods: Count


class GasRetailMetricCoverage(ResponseDTO):
    metric: GasRetailMetric
    counts: list[GasRetailAuditCount] = Field(max_length=6)
    audits_url: str


class GasRetailCoverageIssue(ResponseDTO):
    period: GasRetailPeriod
    metric: GasRetailMetric
    status: GasRetailAuditStatus
    note: str
    audit_url: str


class GasRetailRevisionCoverage(GasRetailRevision):
    coverage: list[GasRetailMetricCoverage] = Field(max_length=2)
    issue_count: Count
    issues: list[GasRetailCoverageIssue] = Field(max_length=10)
    issues_truncated: bool


class GasRetailRevisionsResponse(ResponseDTO):
    total: Count
    limit: PageLimit
    offset: PageOffset
    items: list[GasRetailRevisionCoverage] = Field(max_length=100)


class GasReferenceObservation(ResponseDTO):
    observed_name: str
    designation: Literal["gas_cur"]
    evidence_on: str
    page: Annotated[int, Field(ge=0, le=200)]
    review_note: str
    source: GasRetailSourceMetadata


class GasReferenceMarketer(ResponseDTO):
    marketer_id: GasRetailId
    observations: list[GasReferenceObservation] = Field(max_length=100)


class GasReferenceMarketersResponse(GasRetailPage):
    items: list[GasReferenceMarketer] = Field(max_length=100)

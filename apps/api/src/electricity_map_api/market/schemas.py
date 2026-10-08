"""Pydantic request DTOs and complete public response contracts."""

from datetime import date
from typing import Annotated, Literal, Self

from electricity_map_domain import EnergySector
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from electricity_map_api.schemas import ResponseDTO

Period = Annotated[str, Field(pattern=r"^20[0-9]{2}T[1-4]$", min_length=6, max_length=6, examples=["2024T4"])]
CommunityCode = Annotated[
    str,
    Field(pattern=r"^(0[1-9]|1[0-9])$", min_length=2, max_length=2, description="Two-digit INE code", examples=["13"]),
]


def registered_marketer(value: str) -> str:
    if value == "R2-000":
        raise ValueError("R2-000 denotes direct consumers, not a registered marketer")
    return value


MarketerCode = Annotated[
    str,
    Field(
        pattern=r"^R2-[0-9]+$",
        max_length=32,
        description="CNMC R2 code; R2-000 is excluded",
        examples=["R2-001"],
        json_schema_extra={"not": {"const": "R2-000"}},
    ),
    AfterValidator(registered_marketer),
]
Supplies = Annotated[int, Field(ge=0)]
Share = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Denominator = Literal["supplies_with_registered_marketer"]


class SectorQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sector: EnergySector = Field(default=EnergySector.ELECTRICITY, description="Energy sector")


class QuarterQuery(SectorQuery):
    period: Period


class SeriesQuery(SectorQuery):
    community_code: CommunityCode | None = Field(default=None, description="Omit for national totals")


class SharesQuery(QuarterQuery):
    community_code: CommunityCode | None = Field(default=None, description="Omit for national totals")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum number of marketers")
    offset: int = Field(default=0, ge=0, le=10_000)


class ShareSeriesQuery(SeriesQuery):
    start_period: Period | None = Field(default=None, description="Inclusive first quarter")
    end_period: Period | None = Field(default=None, description="Inclusive last quarter; must be >= start_period")
    limit: int = Field(default=120, ge=1, le=120, description="Maximum number of loaded quarters")
    offset: int = Field(default=0, ge=0, le=10_000)

    @model_validator(mode="after")
    def ordered_periods(self) -> Self:
        if self.start_period is not None and self.end_period is not None and self.start_period > self.end_period:
            raise ValueError("Quarter range is reversed")
        return self


class SourceMetadata(ResponseDTO):
    source_url: str
    license_id: str
    license_url: str
    conditions_url: str
    attribution: str


class RevisionMetadata(SourceMetadata):
    metadata_modified: str


class Quarter(RevisionMetadata):
    period: Period
    package_name: str
    resource_id: str
    row_count: Supplies


class QuartersResponse(ResponseDTO):
    sector: EnergySector
    quarters: list[Quarter] = Field(max_length=120)


class MarketerShare(ResponseDTO):
    marketer_code: MarketerCode
    observed_name: str | None
    supplies: Supplies
    share: Share


class CategoryTotals(ResponseDTO):
    marketer_supplies: Supplies
    direct_consumer_supplies: Supplies
    unavailable_supplies: Supplies


class SharesResponse(RevisionMetadata, CategoryTotals):
    sector: EnergySector
    period: Period
    community_code: CommunityCode | None
    denominator: Denominator
    items: list[MarketerShare] = Field(max_length=100)


class SuppliesPoint(ResponseDTO):
    period: Period
    supplies: Supplies
    metadata_modified: str


class SeriesResponse(ResponseDTO):
    sector: EnergySector
    marketer_code: MarketerCode
    community_code: CommunityCode | None
    source_url: str | None
    license_id: str | None
    license_url: str | None
    conditions_url: str | None
    attribution: str | None
    series: list[SuppliesPoint] = Field(max_length=120)


class ShareSeriesPoint(RevisionMetadata, CategoryTotals):
    period: Period
    supplies: Supplies
    share: Share | None
    package_name: str
    resource_id: str


class ShareSeriesResponse(ResponseDTO):
    sector: EnergySector
    marketer_code: MarketerCode
    community_code: CommunityCode | None
    denominator: Denominator
    limit: int = Field(ge=1, le=120)
    offset: int = Field(ge=0, le=10_000)
    series: list[ShareSeriesPoint] = Field(max_length=120)


class CommunityShare(CategoryTotals):
    community_code: CommunityCode
    supplies: Supplies
    share: Share | None


class CommunitySharesResponse(RevisionMetadata):
    sector: EnergySector
    period: Period
    marketer_code: MarketerCode
    denominator: Denominator
    items: list[CommunityShare] = Field(max_length=19)


class ReferenceMarketer(ResponseDTO):
    marketer_code: MarketerCode
    name: str
    territorial_limit: Literal["ceuta", "melilla"] | None


class ReferenceMarketersResponse(ResponseDTO):
    sector: EnergySector
    snapshot_date: date
    scope: Literal["reference_marketers"]
    designation_source_url: str | None
    code_source_url: str | None
    code_source_period: Period | None
    code_source_metadata_modified: str | None
    attribution: str | None
    items: list[ReferenceMarketer] = Field(max_length=8)

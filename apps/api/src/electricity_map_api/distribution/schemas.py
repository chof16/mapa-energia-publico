"""Contracts for positive, incomplete provincial distributor presence."""

from datetime import date
from typing import Annotated, Literal

from electricity_map_domain import EnergySector
from pydantic import BaseModel, ConfigDict, Field

from electricity_map_api.schemas import ResponseDTO

ProvinceCode = Annotated[
    str,
    Field(
        pattern=r"^(0[1-9]|[1-4][0-9]|5[0-2])$",
        min_length=2,
        max_length=2,
        description="Two-digit INE province code, including Ceuta and Melilla",
        examples=["33"],
    ),
]


class ProvinceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sector: EnergySector = Field(default=EnergySector.ELECTRICITY)


class CoverageEvidence(ResponseDTO):
    source_title: str
    source_url: str
    published_on: date | None
    checked_on: date
    geographic_claim: str
    confidence: Literal["official_document", "group_first_party_reported", "other_operator_reported"]


class AssociationEvidence(ResponseDTO):
    source_title: str
    source_url: str
    published_on: date | None
    checked_on: date
    relationship_claim: str


class CorAssociation(ResponseDTO):
    marketer_code: str
    marketer_name: str
    evidence: AssociationEvidence


class CorporateGroupAssociation(ResponseDTO):
    group_name: str
    evidence: AssociationEvidence


class DistributorPresence(ResponseDTO):
    distributor_code: str
    distributor_name: str
    registry_source_url: str
    evidence: CoverageEvidence
    cor: CorAssociation | None
    corporate_group: CorporateGroupAssociation | None


class ProvincePresenceResponse(ResponseDTO):
    sector: EnergySector
    province_code: ProvinceCode
    snapshot_date: date
    scope: Literal["provincial_presence"]
    complete: Literal[False]
    items: list[DistributorPresence]


class ProvincePresenceSummaryItem(ResponseDTO):
    province_code: ProvinceCode
    documented_distributor_count: int = Field(ge=1)


class ProvincePresenceSummaryResponse(ResponseDTO):
    sector: EnergySector
    snapshot_date: date
    scope: Literal["documented_provincial_presence"]
    complete: Literal[False]
    items: list[ProvincePresenceSummaryItem] = Field(max_length=52)

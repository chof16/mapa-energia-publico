"""Shared DTOs, source metadata and bounded query/response fields."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Count = Annotated[int, Field(ge=0)]
Share = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
PageLimit = Annotated[int, Field(ge=1, le=100)]
PageOffset = Annotated[int, Field(ge=0, le=10_000)]


class QueryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PageQuery(QueryDTO):
    limit: PageLimit = Field(default=50, description="Maximum number of items")
    offset: PageOffset = 0


class ResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceMetadata(ResponseDTO):
    source_url: str
    license_id: str
    license_url: str
    conditions_url: str
    attribution: str


class RevisionMetadata(SourceMetadata):
    metadata_modified: str


class ErrorResponse(ResponseDTO):
    detail: str


class ValidationIssue(ResponseDTO):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorResponse(ResponseDTO):
    detail: list[ValidationIssue]


VALIDATION_RESPONSES = {
    422: {"model": ValidationErrorResponse, "description": "Invalid request parameters"},
}

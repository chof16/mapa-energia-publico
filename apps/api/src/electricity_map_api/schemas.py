"""Shared DTOs for HTTP errors."""

from pydantic import BaseModel, ConfigDict


class ResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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

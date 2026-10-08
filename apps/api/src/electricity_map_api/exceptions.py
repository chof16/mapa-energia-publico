"""Translate application errors into the documented HTTP contract."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from electricity_map_api.schemas import ErrorResponse, ValidationErrorResponse, ValidationIssue


class APIError(Exception):
    status_code = 500
    detail = "Internal server error"
    headers: dict[str, str] | None = None


class DatabaseUnavailable(APIError):
    status_code = 503
    detail = "Market database is unavailable"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail


async def api_error_handler(request: Request, error: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code, content=ErrorResponse(detail=error.detail).model_dump(), headers=error.headers
    )


async def validation_error_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    # Keep errors stable and avoid reflecting raw input or non-JSON validator context.
    response = ValidationErrorResponse(
        detail=[
            ValidationIssue(loc=list(issue["loc"]), msg=issue["msg"], type=issue["type"]) for issue in error.errors()
        ]
    )
    return JSONResponse(status_code=422, content=response.model_dump())

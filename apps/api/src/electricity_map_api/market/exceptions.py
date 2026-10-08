"""Market-specific application errors."""

from electricity_map_api.exceptions import APIError


class QuarterNotLoaded(APIError):
    status_code = 404
    detail = "Quarter is not loaded"

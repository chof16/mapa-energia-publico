"""Gas-specific application errors."""

from electricity_map_api.exceptions import APIError


class GasSourceNotLoaded(APIError):
    status_code = 404
    detail = "Gas source is not loaded"

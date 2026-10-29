"""Gas retail errors handled by the shared API boundary."""

from electricity_map_api.exceptions import APIError


class GasRetailNotLoaded(APIError):
    status_code = 404
    detail = "Gas retail revision is not loaded"


class GasRetailMarketerNotFound(APIError):
    status_code = 404
    detail = "Reviewed gas retailer is not available in this revision"


class GasRetailEvidenceLimit(APIError):
    status_code = 503
    detail = "Gas retail evidence exceeds the response safety limit"

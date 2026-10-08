"""Domain types independent from FastAPI and external data sources."""

from enum import StrEnum


class EnergySector(StrEnum):
    """Supported sectors without assuming all future data is electrical."""

    ELECTRICITY = "electricity"
    GAS = "gas"


__all__ = ["EnergySector"]

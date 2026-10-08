"""Typed database dependency for market endpoints."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from electricity_map_api.database import get_session

MarketSession = Annotated[Session, Depends(get_session)]

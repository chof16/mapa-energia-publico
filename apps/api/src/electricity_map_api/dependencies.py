"""Typed read-only database dependency shared by API features."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from electricity_map_api.database import get_session

DatabaseSession = Annotated[Session, Depends(get_session)]

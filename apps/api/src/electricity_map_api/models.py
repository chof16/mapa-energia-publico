"""Shared SQLAlchemy declarative registry; schema creation belongs to ingestion."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

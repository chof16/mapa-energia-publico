"""Read models for source projections and indexed normalized market facts."""

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from electricity_map_api.models import Base


class MarketSector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text)


class MarketPeriod(Base):
    __tablename__ = "periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)


class MarketImport(Base):
    __tablename__ = "loads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector_id: Mapped[int] = mapped_column(Integer)
    period_id: Mapped[int] = mapped_column(Integer)
    metadata_modified: Mapped[str] = mapped_column(Text)


class MarketCompany(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector_id: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)


class MarketCompanyName(Base):
    __tablename__ = "company_names"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(Text)


class MarketFact(Base):
    __tablename__ = "market_rows"

    load_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_row_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketer_name_id: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(Text)
    community_code: Mapped[str] = mapped_column(Text)
    supplies: Mapped[int] = mapped_column(Integer)


class MarketLoad(Base):
    __tablename__ = "loads_view"

    sector: Mapped[str] = mapped_column(Text, primary_key=True)
    period: Mapped[str] = mapped_column(Text, primary_key=True)
    package_name: Mapped[str] = mapped_column(Text)
    resource_id: Mapped[str] = mapped_column(Text)
    metadata_modified: Mapped[str] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(Integer)
    loaded_at: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    license_id: Mapped[str] = mapped_column(Text)
    license_url: Mapped[str] = mapped_column(Text)
    conditions_url: Mapped[str] = mapped_column(Text)
    attribution: Mapped[str] = mapped_column(Text)


class MarketRow(Base):
    __tablename__ = "market_rows_view"

    sector: Mapped[str] = mapped_column(Text, primary_key=True)
    period: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    distributor_code: Mapped[str] = mapped_column(Text)
    distributor_name: Mapped[str] = mapped_column(Text)
    marketer_code: Mapped[str | None] = mapped_column(Text)
    marketer_name: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    tariff: Mapped[str] = mapped_column(Text)
    community_code: Mapped[str] = mapped_column(Text)
    supplies: Mapped[int] = mapped_column(Integer)
    energy_kwh: Mapped[int] = mapped_column(Integer)

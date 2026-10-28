"""Historical gas network evidence for the distributor map."""

from sqlalchemy import BigInteger, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from electricity_map_api.models import Base


class GasNetworkLoad(Base):
    __tablename__ = "gas_network_loads"

    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    period: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    download_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(Text)
    published_on: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(Text)
    reuse_status: Mapped[str] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(Integer)


class GasNetworkRow(Base):
    __tablename__ = "gas_network_rows"

    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_row_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    province_code: Mapped[str] = mapped_column(Text)
    municipality_name: Mapped[str] = mapped_column(Text)
    distributor_name: Mapped[str] = mapped_column(Text)
    supply_points: Mapped[int] = mapped_column(BigInteger)

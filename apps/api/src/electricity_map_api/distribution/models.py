"""Read models for reviewed distribution evidence; ingestion owns the schema."""

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from electricity_map_api.models import Base


class DistributionSnapshot(Base):
    __tablename__ = "snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[str] = mapped_column(Text)
    complete: Mapped[int] = mapped_column(Integer)


class DistributorIdentity(Base):
    __tablename__ = "distributor_identity"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    registry_source_url: Mapped[str] = mapped_column(Text)


class GroupAssociation(Base):
    __tablename__ = "group_association"

    distributor_code: Mapped[str] = mapped_column(Text, ForeignKey("distributor_identity.code"), primary_key=True)
    group_name: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str] = mapped_column(Text)


class ClaimDecision(Base):
    __tablename__ = "claim_decision"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    province_code: Mapped[str] = mapped_column(Text)
    distributor_code: Mapped[str] = mapped_column(Text, ForeignKey("distributor_identity.code"))
    status: Mapped[str] = mapped_column(Text)
    decision_reason: Mapped[str] = mapped_column(Text)
    review_source_url: Mapped[str] = mapped_column(Text)
    checked_on: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str | None] = mapped_column(Text)

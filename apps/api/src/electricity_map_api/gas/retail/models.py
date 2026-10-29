"""Read mappings for the explicitly installed gas retail schema."""

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from electricity_map_api.models import Base


class GasRetailLoad(Base):
    __tablename__ = "gas_retail_loads"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    reviewed_on: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[str] = mapped_column(Text)
    reuse_status: Mapped[str] = mapped_column(Text)


class GasRetailSource(Base):
    __tablename__ = "gas_retail_sources"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(Text)
    published_on: Mapped[str | None] = mapped_column(Text)
    retrieved_on: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer)
    reuse_status: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text)


class GasRetailEntity(Base):
    __tablename__ = "gas_retail_entities"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    gas_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    review_note: Mapped[str] = mapped_column(Text)


class GasRetailMapping(Base):
    __tablename__ = "gas_retail_mappings"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    mapping_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text)
    observed_name: Mapped[str] = mapped_column(Text)
    gas_id: Mapped[str] = mapped_column(Text)
    review_note: Mapped[str] = mapped_column(Text)


class GasRetailAudit(Base):
    __tablename__ = "gas_retail_audits"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    period: Mapped[str] = mapped_column(Text, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text)
    source_ids_json: Mapped[str] = mapped_column(Text)
    pages_json: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)


class GasRetailQuarter(Base):
    __tablename__ = "gas_retail_quarters"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    gas_id: Mapped[str] = mapped_column(Text, primary_key=True)
    period: Mapped[str] = mapped_column(Text, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    scope: Mapped[str] = mapped_column(Text, primary_key=True)
    unit: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text)
    value: Mapped[str | None] = mapped_column(Text)
    upper_bound: Mapped[str | None] = mapped_column(Text)
    missing_months_json: Mapped[str] = mapped_column(Text)
    input_statuses_json: Mapped[str] = mapped_column(Text)
    observation_ids_json: Mapped[str] = mapped_column(Text)


class GasRetailObservation(Base):
    __tablename__ = "gas_retail_observations"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    observation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text)
    mapping_id: Mapped[str] = mapped_column(Text)
    month: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    table_label: Mapped[str] = mapped_column(Text)
    source_row: Mapped[str] = mapped_column(Text)
    raw_value: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    value: Mapped[str | None] = mapped_column(Text)
    upper_bound: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str] = mapped_column(Text)


class GasRetailCatalogue(Base):
    __tablename__ = "gas_retail_catalogue"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    gas_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    observed_name: Mapped[str] = mapped_column(Text)
    designation: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    evidence_on: Mapped[str] = mapped_column(Text)
    review_note: Mapped[str] = mapped_column(Text)


class GasRetailSourceAudit(Base):
    __tablename__ = "gas_retail_source_audits"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    period: Mapped[str] = mapped_column(Text, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text)
    pages_json: Mapped[str] = mapped_column(Text)
    table_review_status: Mapped[str] = mapped_column(Text)
    retailer_coverage: Mapped[str] = mapped_column(Text)
    geographic_scope: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)


class GasRetailObservationDetail(Base):
    __tablename__ = "gas_retail_observation_details"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    observation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    original_unit: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(Text)


class GasRetailUnresolvedObservation(Base):
    __tablename__ = "gas_retail_unresolved_observations"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    observation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text)
    mapping_id: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    table_label: Mapped[str] = mapped_column(Text)
    source_row: Mapped[str] = mapped_column(Text)
    raw_value: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    review_note: Mapped[str] = mapped_column(Text)


class GasRetailReviewRecord(Base):
    __tablename__ = "gas_retail_review_records"
    load_id: Mapped[str] = mapped_column(Text, primary_key=True)
    record_id: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)

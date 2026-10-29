"""Explicit ingestion of reviewed private gas retail evidence, never PDF inference."""

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from electricity_map_ingestion import gas_retail_store

MAX_BYTES = 64_000_000
Status = Literal["exact", "zero", "missing", "suppressed", "source_error", "bounded"]
Kind = Literal["retailer", "group", "rest", "total", "direct_consumer", "unknown"]
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,79}$")]
ObservationIdentifier = Annotated[str, Field(pattern=r"^[a-z][a-zA-Z0-9_ -]{0,79}$")]
Text = Annotated[str, Field(min_length=1, max_length=1000)]
ObservationNote = Annotated[str, Field(min_length=1, max_length=4000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Source(Contract):
    source_id: Identifier
    url: Text
    title: Text
    publisher: Literal["CNMC", "CNE", "BOE", "Administración General del Estado"]
    published_on: str | None
    retrieved_on: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    file_name: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_.-]{1,150}$")]
    media_type: Literal["pdf", "html"]
    byte_size: Annotated[int, Field(ge=1, le=25_000_000)]
    page_count: Annotated[int, Field(ge=0, le=200)]
    reuse_status: Literal["review_pending"]
    notes: Text

    @field_validator("published_on", "retrieved_on")
    @classmethod
    def valid_date(cls, value: str | None) -> str | None:
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Expected ISO date")
        return value

    @field_validator("url")
    @classmethod
    def official_url(cls, value: str) -> str:
        url = urlsplit(value)
        if url.scheme != "https" or url.netloc not in {"www.cnmc.es", "www.boe.es", "administracion.gob.es"}:
            raise ValueError("Source must use an allowlisted official HTTPS host")
        return value

    @model_validator(mode="after")
    def source_format(self):
        if (self.media_type == "pdf") != (self.page_count > 0):
            raise ValueError("PDF sources require a bounded page count")
        if not self.file_name.endswith("." + self.media_type):
            raise ValueError("Source extension does not match allowed format")
        return self


class Entity(Contract):
    gas_id: Annotated[str, Field(pattern=r"^gas-[a-z0-9-]{1,75}$")]
    name: Text
    kind: Kind
    review_note: Text


class Mapping(Contract):
    mapping_id: Identifier
    source_id: Identifier
    observed_name: Text
    gas_id: str
    review_note: Text


class Audit(Contract):
    period: Annotated[str, Field(pattern=r"^20\d{2}T[1-4]$")]
    metric: Literal["clients", "sales"]
    status: Literal["not_reviewed", "located", "partial", "reviewed", "unavailable", "source_error"]
    source_ids: Annotated[list[Identifier], Field(max_length=10)]
    pages: Annotated[list[Annotated[int, Field(ge=1, le=200)]], Field(max_length=200)]
    note: Text


class Observation(Contract):
    observation_id: ObservationIdentifier
    source_id: Identifier
    mapping_id: Identifier
    month: Annotated[str, Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")]
    metric: Literal["clients", "sales"]
    scope: Literal["liberalised", "whole_market", "regulated"]
    unit: Literal["clients", "MWh", "GWh", "kWh"]
    page: Annotated[int, Field(ge=1, le=200)]
    table_label: Text
    source_row: Text
    raw_value: Annotated[str, Field(max_length=100)]
    status: Status
    value: str | None
    upper_bound: str | None
    review_note: ObservationNote

    @model_validator(mode="after")
    def scalar_contract(self):
        from decimal import Decimal

        from electricity_map_domain.gas_retail import MonthlyValue, aggregate_quarter

        for number in (self.value, self.upper_bound):
            if number is not None and not re.fullmatch(r"(?:0|[1-9]\d{0,15})(?:\.\d{1,6})?", number):
                raise ValueError("Values must be bounded exact decimal strings")
        if (self.metric == "clients") != (self.unit == "clients"):
            raise ValueError("Metric and unit disagree")
        if self.metric == "clients" and any(n is not None and "." in n for n in (self.value, self.upper_bound)):
            raise ValueError("Clients must be integral")
        aggregate_quarter(
            f"{self.month[:4]}T{(int(self.month[-2:]) - 1) // 3 + 1}",
            self.metric,
            [
                MonthlyValue(
                    self.month,
                    self.status,
                    Decimal(self.value) if self.value is not None else None,
                    Decimal(self.upper_bound) if self.upper_bound is not None else None,
                )
            ],
        )
        return self


class CatalogueEntry(Contract):
    gas_id: str
    observed_name: Text
    designation: Literal["gas_cur"]
    source_id: Identifier
    page: Annotated[int, Field(ge=0, le=200)]
    evidence_on: str
    review_note: Text

    @field_validator("evidence_on")
    @classmethod
    def valid_date(cls, value: str) -> str:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("Expected ISO date")
        return value


class SourceAudit(Audit):
    source_id: Identifier
    table_review_status: Literal["reviewed", "partial", "unavailable", "not_reviewed", "source_error"]
    retailer_coverage: Literal["reviewed", "partial", "unknown", "unavailable_in_table"]
    geographic_scope: Text


class UnresolvedObservation(Contract):
    observation_id: ObservationIdentifier
    source_id: Identifier
    mapping_id: Identifier
    period: Annotated[str, Field(pattern=r"^20\d{2}T[1-4]$")]
    metric: Literal["clients", "sales"]
    scope: Literal["liberalised", "whole_market", "regulated"]
    unit: Literal["clients", "MWh", "GWh", "kWh"]
    page: Annotated[int, Field(ge=1, le=200)]
    table_label: Text
    source_row: Text
    raw_value: Annotated[str, Field(max_length=100)]
    status: Literal["source_error"]
    review_note: ObservationNote


class ObservationDetail(Contract):
    observation_id: ObservationIdentifier
    original_unit: Text
    review_status: Literal["reviewed", "partial", "source_error"]


class ReviewRecord(Contract):
    record_id: Identifier
    category: Literal["alias", "identity_event", "issue", "input_file", "source_inventory", "source_audit"]
    payload_json: Annotated[str, Field(min_length=2, max_length=32_000)]


def periods() -> list[str]:
    return [
        f"{year}T{quarter}"
        for year in range(2003, 2027)
        for quarter in range(1, 5)
        if (2003, 4) <= (year, quarter) <= (2026, 1)
    ]


class Evidence(Contract):
    version: Literal[1, 2]
    reviewed_on: str
    complete: Literal[False]
    sources: Annotated[list[Source], Field(max_length=200)]
    entities: Annotated[list[Entity], Field(max_length=20_000)]
    mappings: Annotated[list[Mapping], Field(max_length=20_000)]
    audits: Annotated[list[Audit], Field(min_length=180, max_length=180)]
    observations: Annotated[list[Observation], Field(max_length=100_000)]
    catalogue: Annotated[list[CatalogueEntry], Field(max_length=100)]
    source_audits: Annotated[list[SourceAudit], Field(max_length=2000)] = Field(default_factory=list)
    unresolved_observations: Annotated[list[UnresolvedObservation], Field(max_length=10_000)] = Field(
        default_factory=list
    )
    observation_details: Annotated[list[ObservationDetail], Field(max_length=100_000)] = Field(default_factory=list)
    review_records: Annotated[list[ReviewRecord], Field(max_length=30_000)] = Field(default_factory=list)

    @field_validator("reviewed_on")
    @classmethod
    def valid_date(cls, value: str) -> str:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("Expected ISO date")
        return value

    @model_validator(mode="after")
    def relationships(self):
        sources = {row.source_id: row for row in self.sources}
        entities = {row.gas_id: row for row in self.entities}
        mappings = {row.mapping_id: row for row in self.mappings}
        audits = {(row.period, row.metric): row for row in self.audits}
        if (len(sources), len(entities), len(mappings), len(audits)) != (
            len(self.sources),
            len(self.entities),
            len(self.mappings),
            len(self.audits),
        ) or len({row.observation_id for row in self.observations}) != len(self.observations):
            raise ValueError("Duplicate evidence identifiers")
        if set(audits) != {(period, metric) for period in periods() for metric in ("clients", "sales")}:
            raise ValueError("Independent audits for all 90 quarters are required")
        name_keys = set()
        for row in self.mappings:
            if row.source_id not in sources or row.gas_id not in entities:
                raise ValueError("Mapping references unknown evidence")
            key = (
                (row.source_id, row.observed_name, row.gas_id)
                if self.version == 2
                else (row.source_id, row.observed_name)
            )
            if key in name_keys:
                raise ValueError("Ambiguous name mapping")
            name_keys.add(key)
        for row in self.audits:
            if any(source not in sources for source in row.source_ids):
                raise ValueError("Audit references unknown source")
            if row.status in {"reviewed", "partial", "unavailable", "source_error"} and not row.source_ids:
                raise ValueError("Audited conclusions need evidence")
            if row.pages and (
                not row.source_ids or max(row.pages) > max(sources[s].page_count for s in row.source_ids)
            ):
                raise ValueError("Audit page outside source")
        for row in self.observations:
            mapping = mappings.get(row.mapping_id)
            if mapping is None or mapping.source_id != row.source_id:
                raise ValueError("Observation requires an exact source-specific reviewed mapping")
            if row.page > sources[row.source_id].page_count:
                raise ValueError("Observation page outside source")
            period = f"{row.month[:4]}T{(int(row.month[-2:]) - 1) // 3 + 1}"
            audit = audits.get((period, row.metric))
            if audit is None or audit.status not in {"reviewed", "partial", "source_error"}:
                raise ValueError("Observation cannot come from an unreviewed period/metric")
            if row.source_id not in audit.source_ids:
                raise ValueError("Observation source missing from audit")
        for row in self.catalogue:
            if row.gas_id not in entities or entities[row.gas_id].kind != "retailer" or row.source_id not in sources:
                raise ValueError("Invalid independent CUR catalogue evidence")
            if row.page > sources[row.source_id].page_count:
                raise ValueError("Catalogue page outside source")
        if len({(row.gas_id, row.source_id) for row in self.catalogue}) != len(self.catalogue):
            raise ValueError("Duplicate catalogue evidence")
        extras = (self.source_audits, self.unresolved_observations, self.observation_details, self.review_records)
        if self.version == 1 and any(extras):
            raise ValueError("Review extensions require evidence version 2")
        if self.version == 2:
            source_audits = {(r.source_id, r.period, r.metric): r for r in self.source_audits}
            if len(source_audits) != len(self.source_audits):
                raise ValueError("Duplicate source audit")
            for row in self.source_audits:
                if row.source_id not in sources or row.source_ids != [row.source_id]:
                    raise ValueError("Source audit requires its own source")
                if (row.period, row.metric) not in audits or any(
                    p > sources[row.source_id].page_count for p in row.pages
                ):
                    raise ValueError("Invalid source audit period or page")
            for audit in self.audits:
                children = [r for r in self.source_audits if (r.period, r.metric) == (audit.period, audit.metric)]
                if set(audit.source_ids) != {r.source_id for r in children} or not children:
                    raise ValueError("Coverage summary must include every source audit")
                if audit.status == "reviewed" and any(
                    r.status != "reviewed" or r.retailer_coverage != "reviewed" for r in children
                ):
                    raise ValueError("Coverage summary cannot promote partial source evidence")
            all_ids = {r.observation_id for r in self.observations}
            for row in self.unresolved_observations:
                if row.observation_id in all_ids:
                    raise ValueError("Duplicate unresolved observation")
                all_ids.add(row.observation_id)
                mapping = mappings.get(row.mapping_id)
                if (
                    mapping is None
                    or mapping.source_id != row.source_id
                    or row.page > sources[row.source_id].page_count
                ):
                    raise ValueError("Invalid unresolved observation provenance")
                if (row.metric == "clients") != (row.unit == "clients"):
                    raise ValueError("Unresolved metric and unit disagree")
            for row in [*self.observations, *self.unresolved_observations]:
                period = (
                    row.period
                    if isinstance(row, UnresolvedObservation)
                    else f"{row.month[:4]}T{(int(row.month[-2:]) - 1) // 3 + 1}"
                )
                audit = source_audits.get((row.source_id, period, row.metric))
                if audit is None or audit.status not in {"reviewed", "partial", "source_error"}:
                    raise ValueError("Observation requires a usable source-specific audit")
            if (
                len(self.observation_details) != len(all_ids)
                or {r.observation_id for r in self.observation_details} != all_ids
            ):
                raise ValueError("Every cell requires exactly one review detail")
            detail_by_id = {r.observation_id: r for r in self.observation_details}
            for row in self.observations:
                period = f"{row.month[:4]}T{(int(row.month[-2:]) - 1) // 3 + 1}"
                if (
                    audits[period, row.metric].status == "reviewed"
                    and detail_by_id[row.observation_id].review_status != "reviewed"
                ):
                    raise ValueError("Coverage summary cannot promote an unreviewed cell")
            if len({r.record_id for r in self.review_records}) != len(self.review_records):
                raise ValueError("Duplicate review record")
        return self


def read_json_object(path: Path) -> dict:
    if not 1 <= path.stat().st_size <= MAX_BYTES:
        raise ValueError("Evidence size limit")
    with path.open("rb") as stream:
        body = stream.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES or not body.lstrip().startswith(b"{"):
        raise ValueError("Expected a bounded JSON object")
    # Bound nesting and structural elements before entering the JSON decoder.
    quoted = escaped = False
    depth = elements = 0
    for byte in body:
        if escaped:
            escaped = False
        elif quoted and byte == 92:
            escaped = True
        elif byte == 34:
            quoted = not quoted
        elif not quoted:
            if byte in (123, 91):
                depth += 1
                elements += 1
            elif byte in (125, 93):
                depth -= 1
            if depth > 16 or elements > 300_000:
                raise ValueError("JSON structural limit")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    return json.loads(body, object_pairs_hook=unique_object)


def read_evidence(path: Path) -> Evidence:
    return Evidence.model_validate(read_json_object(path))


def verify_sources(evidence: Evidence, directory: Path) -> None:
    for source in evidence.sources:
        path = directory / source.file_name
        if path.is_symlink() or path.stat().st_size != source.byte_size:
            raise ValueError("Source size mismatch or symlink")
        with path.open("rb") as stream:
            body = stream.read(source.byte_size + 1)
        if len(body) != source.byte_size or hashlib.sha256(body).hexdigest() != source.sha256:
            raise ValueError("Source digest mismatch")
        if source.media_type == "pdf":
            if not body.startswith(b"%PDF-") or b"%%EOF" not in body[-2048:]:
                raise ValueError("Invalid PDF signature/trailer")
        elif not body.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            raise ValueError("Invalid HTML signature")


def require_company_identities(evidence: Evidence) -> None:
    """Source-local extraction IDs must not become the public company catalogue."""
    if evidence.version == 2 and any(entity.gas_id.startswith("gas-cnmc-") for entity in evidence.entities):
        raise ValueError("Resolve source-local extraction IDs with --identities before importing company histories")


def ingest(evidence: Evidence, database: Path) -> str:
    require_company_identities(evidence)
    if database.exists():
        with database.open("rb") as stream:
            if not 16 <= database.stat().st_size <= 20 * 1024**3 or stream.read(16) != b"SQLite format 3\x00":
                raise ValueError("Invalid SQLite destination")
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        migration = gas_retail_store.needs_entity_migration(connection)
        connection.execute("PRAGMA foreign_keys=" + ("OFF" if migration else "ON"))
        connection.execute("BEGIN IMMEDIATE")
        if migration:
            gas_retail_store.migrate_entities(connection)
        gas_retail_store.initialize(connection)
        load_id = gas_retail_store.write_load(connection, evidence)
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Foreign key verification failed")
        connection.commit()
        return load_id
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--identities", type=Path, help="Explicit cross-report company identity review")
    args = parser.parse_args()
    evidence = read_evidence(args.evidence)
    verify_sources(evidence, args.sources_dir)
    if args.identities:
        from electricity_map_ingestion.gas_retail_identity import read_registry, reconcile

        evidence = reconcile(evidence, read_registry(args.identities))
    require_company_identities(evidence)
    load_id = gas_retail_store.revision_id(evidence) if args.dry_run else ingest(evidence, args.database)
    print(
        json.dumps(
            {
                "load_id": load_id,
                "dry_run": args.dry_run,
                "observations": len(evidence.observations),
                "unresolved_months": len(evidence.unresolved_observations),
                "source_audits": len(evidence.source_audits),
                "audits": len(evidence.audits),
                "complete": False,
            }
        )
    )


if __name__ == "__main__":
    main()

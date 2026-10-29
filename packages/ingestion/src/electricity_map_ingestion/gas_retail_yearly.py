"""Validate yearly review CSVs and prepare versioned gas evidence, without writes to a database."""

import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from electricity_map_ingestion.gas_retail import Evidence, periods, read_evidence, verify_sources
from electricity_map_ingestion.gas_retail_store import revision_id, rows_for_load

MONTHLY = (
    "company_id company_name observed_name entity_kind year quarter month metric market_scope raw_value value "
    "value_status upper_bound original_unit value_mwh source_id source_url source_sha256 publication_date "
    "pdf_page table_label source_row observation_id review_status notes"
).split()
QUARTERLY = (
    "company_id company_name observed_name entity_kind year quarter metric market_scope value value_status "
    "upper_bound upper_bound_exclusive original_unit value_mwh upper_bound_mwh source_id source_url source_sha256 "
    "publication_date pdf_pages table_label source_rows observation_ids months missing_months review_status notes"
).split()
AUDIT = (
    "year quarter metric source_id source_title source_url source_sha256 publication_date pdf_pages market_scope "
    "original_unit review_status table_review_status retailer_coverage monthly_observations quarterly_observations "
    "geographic_scope notes"
).split()
ALIASES = (
    "company_id company_name observed_name entity_kind source_id source_url source_sha256 pdf_page "
    "identity_review_status supporting_evidence notes"
).split()
INVENTORY = (
    "source_id file_name reporting_year reporting_periods title source_url source_sha256 publication_date "
    "draft_inventory_date_unverified byte_size pages encrypted copy_allowed validation_status reuse_status"
).split()
IDENTITY_SOURCES = "source_id file_name title url sha256 byte_size page_count published_on reuse_status".split()


def read_csv(path: Path, fields: list[str]) -> tuple[list[dict[str, str]], dict]:
    """Check bounded UTF-8 text and fixed columns before accepting CSV records."""
    if path.is_symlink() or path.suffix != ".csv" or not 1 <= path.stat().st_size <= 12_000_000:
        raise ValueError(f"Invalid CSV file: {path.name}")
    body = path.read_bytes()
    if len(body) > 12_000_000 or b"\x00" in body:
        raise ValueError("CSV byte limit or NUL")
    text = body.decode("utf-8-sig")
    if text.splitlines()[0] != ",".join(fields):
        raise ValueError(f"Unexpected CSV header: {path.name}")
    csv.field_size_limit(32_000)
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    result = []
    for row in reader:
        if len(result) >= 100_000 or set(row) != set(fields) or any(v is None for v in row.values()):
            raise ValueError("CSV row limit or malformed columns")
        result.append(row)
    return result, dict(
        file_name=path.name, sha256=hashlib.sha256(body).hexdigest(), byte_size=len(body), rows=len(result)
    )


def period(row: dict) -> str:
    value = f"{row['year']}T{row['quarter']}"
    if value not in periods():
        raise ValueError("CSV period outside requested history")
    return value


def unit(row: dict) -> str:
    original = row["original_unit"]
    if row["metric"] == "clients" and original in {"clients", "Nº Clientes", "Clientes", "Número de Clientes"}:
        return "clients"
    if row["metric"] == "sales" and original in {"MWh", "GWh", "kWh"}:
        return original
    raise ValueError("Unsupported original unit")


def page_list(value: str) -> list[int]:
    return [int(p) for p in value.split(";") if p]


def verify_quarters(evidence: Evidence, expected: list[dict]) -> None:
    actual = {tuple(row[1:7]): row for row in rows_for_load(evidence, "verification")["gas_retail_quarters"]}
    seen = set()
    for row in expected:
        key = (row["source_id"], row["company_id"], period(row), row["metric"], row["market_scope"], unit(row))
        if key not in actual or key in seen:
            raise ValueError(f"Missing or repeated derived quarter: {key}")
        seen.add(key)
        derived = actual[key]
        for index, field in ((7, "value_status"), (8, "value"), (9, "upper_bound")):
            if (derived[index] or "") != row[field]:
                raise ValueError(f"Quarter mismatch {key} {field}: {derived[index]} != {row[field]}")
        if set(json.loads(derived[10])) != set(filter(None, row["missing_months"].split(";"))):
            raise ValueError(f"Quarter missing-month mismatch: {key}")
        if set(json.loads(derived[12])) != set(filter(None, row["observation_ids"].split(";"))):
            raise ValueError(f"Quarter provenance mismatch: {key}")
    if len(actual) != len(seen):
        raise ValueError("Quarter coverage mismatch")


def prepare(directory: Path, base: Evidence) -> tuple[Evidence, dict]:
    inputs = []

    def read(name, fields):
        rows, manifest = read_csv(directory / name, fields)
        inputs.append(manifest)
        return rows

    inventory = read("source_inventory.csv", INVENTORY)
    identity_sources = read("identity_sources.csv", IDENTITY_SOURCES)
    aliases = read("company_aliases.csv", ALIASES)
    events = read("identity_events.csv", "event_id company_id company_name decision evidence".split())
    issues = read("unresolved_issues.csv", "issue_id source_id period metric issue details".split())
    monthly, quarterly, source_audits = [], [], []
    for year in range(2003, 2027):
        for suffix, fields, target in (
            ("monthly", MONTHLY, monthly),
            ("quarterly", QUARTERLY, quarterly),
            ("audit", AUDIT, source_audits),
        ):
            rows = read(f"gas_{year}_{suffix}.csv", fields)
            if any(row["year"] != str(year) for row in rows):
                raise ValueError("Row in wrong annual file")
            target.extend(rows)
    sources = {s.source_id: s.model_dump() for s in base.sources}
    for row in inventory:
        source = sources[row["source_id"]]
        for csv_key, source_key in (("source_url", "url"), ("source_sha256", "sha256"), ("file_name", "file_name")):
            if row[csv_key] != source[source_key]:
                raise ValueError("Source inventory identity mismatch")
        if int(row["byte_size"]) != source["byte_size"] or int(row["pages"]) != source["page_count"]:
            raise ValueError("Source inventory size/page mismatch")
        source["published_on"] = row["publication_date"] or None
    for row in identity_sources:
        source = sources.get(row["source_id"])
        if source is None:
            source = dict(
                source_id=row["source_id"],
                publisher="CNMC",
                retrieved_on=base.reviewed_on,
                media_type="pdf",
                notes="Evidencia de identidad de la revisión anual; reutilización pendiente.",
            )
        for key in ("file_name", "title", "url", "sha256", "reuse_status"):
            source[key] = row[key]
        source.update(
            byte_size=int(row["byte_size"]), page_count=int(row["page_count"]), published_on=row["published_on"] or None
        )
        sources[row["source_id"]] = source

    def provenance(row):
        source = sources[row["source_id"]]
        if row["source_url"] != source["url"] or row["source_sha256"] != source["sha256"]:
            raise ValueError("CSV source provenance mismatch")
        if "publication_date" in row and (row["publication_date"] or None) != source["published_on"]:
            raise ValueError("CSV publication date mismatch")

    entities = {e.gas_id: e.model_dump() for e in base.entities if e.gas_id in {c.gas_id for c in base.catalogue}}
    mappings = {}
    for row in aliases:
        provenance(row)
        if row["identity_review_status"] not in {"source_local_identity", "reviewed_identity"}:
            raise ValueError("Unsupported identity review status")
        if not 1 <= int(row["pdf_page"]) <= sources[row["source_id"]]["page_count"]:
            raise ValueError("Alias page outside source")
        encoded = row["supporting_evidence"]
        if encoded.count("[") > 20 or encoded.count("{") > 100:
            raise ValueError("Identity reference complexity limit")
        refs = json.loads(encoded)
        if not isinstance(refs, list) or (row["identity_review_status"] == "reviewed_identity" and not refs):
            raise ValueError("Documented identities require evidence")
        for ref in refs:
            if ref["source_id"] not in sources:
                raise ValueError("Unknown identity evidence")
            for page in ref.get("pdf_pages", [ref.get("pdf_page")]):
                if page is not None and not 1 <= int(page) <= sources[ref["source_id"]]["page_count"]:
                    raise ValueError("Identity evidence page outside source")
        entity = dict(
            gas_id=row["company_id"],
            name=row["company_name"],
            kind=row["entity_kind"],
            review_note=row["identity_review_status"] + ": " + row["notes"],
        )
        if entity["gas_id"] in entities and entities[entity["gas_id"]] != entity:
            raise ValueError("Inconsistent company identity")
        entities[entity["gas_id"]] = entity
        key = row["source_id"], row["observed_name"], row["company_id"]
        mapping_id = "map-" + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:32]
        if key in mappings:
            raise ValueError("Duplicate alias decision")
        mappings[key] = dict(
            mapping_id=mapping_id,
            source_id=row["source_id"],
            observed_name=row["observed_name"],
            gas_id=row["company_id"],
            review_note=entity["review_note"],
        )
    observations, unresolved, details = [], [], []
    for row in monthly:
        provenance(row)
        p = period(row)
        key = row["source_id"], row["observed_name"], row["company_id"]
        if key not in mappings or entities[row["company_id"]]["kind"] != row["entity_kind"]:
            raise ValueError("Observation without exact identity decision")
        original_unit = unit(row)
        if row["metric"] == "sales" and row["value"]:
            factor = {"MWh": Decimal(1), "GWh": Decimal(1000), "kWh": Decimal("0.001")}[original_unit]
            if Decimal(row["value_mwh"]) != Decimal(row["value"]) * factor:
                raise ValueError("MWh normalization mismatch")
        elif row["value_mwh"]:
            raise ValueError("Unexpected normalized sales")
        record = dict(
            observation_id=row["observation_id"],
            source_id=row["source_id"],
            mapping_id=mappings[key]["mapping_id"],
            metric=row["metric"],
            scope=row["market_scope"],
            unit=original_unit,
            page=int(row["pdf_page"]),
            table_label=row["table_label"],
            source_row=row["source_row"],
            raw_value=row["raw_value"],
            status=row["value_status"],
            review_note=row["notes"],
        )
        if row["month"]:
            if f"{row['month'][:4]}T{(int(row['month'][-2:]) - 1) // 3 + 1}" != p:
                raise ValueError("Month outside CSV quarter")
            observations.append(
                dict(record, month=row["month"], value=row["value"] or None, upper_bound=row["upper_bound"] or None)
            )
        else:
            if row["value"] or row["upper_bound"]:
                raise ValueError("Unresolved month cannot expose a value")
            unresolved.append(dict(record, period=p))
        details.append(
            dict(
                observation_id=row["observation_id"],
                original_unit=row["original_unit"],
                review_status=row["review_status"],
            )
        )
    audit_rows = []
    by_period = defaultdict(list)
    monthly_groups = defaultdict(list)
    quarterly_groups = defaultdict(list)
    for row in monthly:
        monthly_groups[row["source_id"], period(row), row["metric"]].append(row)
    for row in quarterly:
        provenance(row)
        quarterly_groups[row["source_id"], period(row), row["metric"]].append(row)
        entity = entities[row["company_id"]]
        if entity["kind"] != row["entity_kind"] or entity["name"] != row["company_name"]:
            raise ValueError("Quarter identity mismatch")
        factor = {"clients": Decimal(1), "MWh": Decimal(1), "GWh": Decimal(1000), "kWh": Decimal("0.001")}[unit(row)]
        for original, normalized in (("value", "value_mwh"), ("upper_bound", "upper_bound_mwh")):
            if row["metric"] == "sales" and row[original]:
                if Decimal(row[normalized]) != Decimal(row[original]) * factor:
                    raise ValueError("Quarter MWh normalization mismatch")
            elif row[normalized]:
                raise ValueError("Unexpected quarter MWh value")
    for row in source_audits:
        provenance(row)
        p = period(row)
        key = row["source_id"], p, row["metric"]
        if int(row["monthly_observations"]) != len(monthly_groups[key]) or int(row["quarterly_observations"]) != len(
            quarterly_groups[key]
        ):
            raise ValueError("Source audit cell counts disagree with CSVs")
        record = dict(
            period=p,
            metric=row["metric"],
            status=row["review_status"],
            source_ids=[row["source_id"]],
            pages=page_list(row["pdf_pages"]),
            note=row["notes"],
            source_id=row["source_id"],
            table_review_status=row["table_review_status"],
            retailer_coverage=row["retailer_coverage"],
            geographic_scope=row["geographic_scope"],
        )
        audit_rows.append(record)
        by_period[p, row["metric"]].append(record)
    audits = []
    for p in periods():
        for metric in ("clients", "sales"):
            children = by_period[p, metric]
            if not children:
                raise ValueError("Missing quarter/metric audit")
            statuses = {r["status"] for r in children}
            if statuses == {"reviewed"} and all(r["retailer_coverage"] == "reviewed" for r in children):
                status = "reviewed"
            elif statuses == {"source_error"}:
                status = "source_error"
            elif statuses <= {"not_reviewed", "unavailable"}:
                status = "not_reviewed" if "not_reviewed" in statuses else "unavailable"
            else:
                status = "partial"
            audits.append(
                dict(
                    period=p,
                    metric=metric,
                    status=status,
                    source_ids=sorted({r["source_id"] for r in children}),
                    pages=sorted({v for r in children for v in r["pages"]}),
                    note=(
                        "Resumen conservador de auditorías por fuente. Consultar gas_retail_source_audits "
                        "para revisiones alternativas, cobertura y geografía."
                    ),
                )
            )
    records = []
    for category, rows in (
        ("alias", aliases),
        ("identity_event", events),
        ("issue", issues),
        ("source_inventory", inventory),
        ("source_audit", source_audits),
        ("input_file", inputs),
    ):
        records.extend(
            dict(
                record_id=f"{category}-{i:05}",
                category=category,
                payload_json=json.dumps(row, ensure_ascii=False, sort_keys=True),
            )
            for i, row in enumerate(rows)
        )
    evidence = Evidence.model_validate(
        dict(
            version=2,
            reviewed_on=base.reviewed_on,
            complete=False,
            sources=list(sources.values()),
            entities=list(entities.values()),
            mappings=list(mappings.values()),
            audits=audits,
            observations=observations,
            catalogue=[r.model_dump() for r in base.catalogue],
            source_audits=audit_rows,
            unresolved_observations=unresolved,
            observation_details=details,
            review_records=records,
        )
    )
    verify_quarters(evidence, quarterly)
    return evidence, dict(
        load_id=revision_id(evidence),
        monthly_cells=len(monthly),
        dated_observations=len(observations),
        unresolved_months=len(unresolved),
        quarterly=len(quarterly),
        source_audits=len(audit_rows),
        aliases=len(mappings),
        entities=len(entities),
        validated_files=len(inputs),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--base-evidence", type=Path, required=True)
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence, report = prepare(args.review_dir, read_evidence(args.base_evidence))
    except ValidationError as error:
        parser.exit(1, json.dumps(error.errors(include_input=False, include_context=False)[:5]) + "\n")
    verify_sources(evidence, args.sources_dir)
    if args.output.exists():
        raise FileExistsError("Use a new evidence output path")
    args.output.write_text(evidence.model_dump_json(indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

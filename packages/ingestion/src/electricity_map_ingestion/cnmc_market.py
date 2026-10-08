"""Import the public CNMC Data electricity market series into a local SQLite database."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from electricity_map_ingestion import market_store

API = "https://catalogodatos.cnmc.es/api/3/action"
SOURCE_URL = "https://data.cnmc.es/energia/energia-electrica/energia-y-suministros"
CONDITIONS_URL = "https://data.cnmc.es/condiciones-de-uso"
ATTRIBUTION = "Origen de los datos: Comisión Nacional de los Mercados y la Competencia"
USER_AGENT = "mapa-energia-es/0.1 (proyecto no comercial; datos abiertos CNMC)"
PERIOD = re.compile(r"^20\d{2}T[1-4]$")
DISTRIBUTOR = re.compile(r"^R1-\d+$")
MARKETER = re.compile(r"^R2-\d+$")
EXTINCT = re.compile(r"\s*(?:-\s*EXTINGUIDA\s*-|\(\s*EXTINGUIDA\s*\))\s*$", re.IGNORECASE)
DIRECT_CODES = {"Otros", "000", "R2-000", "Consumidor Directo"}
REQUIRED = {
    "_id",
    "fecha",
    "anno_envio",
    "trimestre_envio",
    "cod_dis",
    "descripcion_distribuidor",
    "cod_com",
    "descripcion_comercializador",
    "tarifa_acceso",
    "ccaa",
    "numero_suministro",
    "energia",
}
COMMUNITIES = {
    "Andalucía": "01",
    "Aragón": "02",
    "Asturias, Principado de": "03",
    "Balears, Illes": "04",
    "Canarias": "05",
    "Cantabria": "06",
    "Castilla y León": "07",
    "Castilla - La Mancha": "08",
    "Cataluña": "09",
    "Comunitat Valenciana": "10",
    "Extremadura": "11",
    "Galicia": "12",
    "Madrid, Comunidad de": "13",
    "Murcia, Región de": "14",
    "Navarra, Comunidad Foral de": "15",
    "País Vasco": "16",
    "Rioja, La": "17",
    "Ceuta": "18",
    "Melilla": "19",
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def _integer(value: Any, field: str, *, signed: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError) as error:
        raise ValueError(f"{field} must be an integer") from error
    lower = -(2**63) if signed else 0
    if not number.is_finite() or number != number.to_integral_value() or not lower <= number <= 2**63 - 1:
        raise ValueError(f"{field} must be a 64-bit integer within its allowed range")
    return int(number)


def _name(value: Any, field: str) -> tuple[str, bool]:
    original = " ".join(_text(value, field).split())
    clean = EXTINCT.sub("", original).strip()
    if not clean:
        raise ValueError(f"{field} contains no company name")
    return clean, clean != original


def _read_json(path: Path, max_bytes: int) -> Any:
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError(f"Missing or oversized JSON file: {path}")
    with path.open("rb") as file:
        body = file.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError(f"Oversized JSON file: {path}")
        prefix = body[:3]
        if prefix not in (b"\xef\xbb\xbf", b"{\n ", b"{\n\t") and prefix[:1] not in (b"{", b"["):
            raise ValueError(f"Not a JSON document: {path}")
        try:
            return json.loads(body.decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid JSON file: {path}") from error


def _extra(package: dict[str, Any], key: str) -> Any:
    return next((item.get("value") for item in package.get("extras", []) if item.get("key") == key), None)


def package_metadata(package: Any) -> tuple[str, str, str, str]:
    if not isinstance(package, dict):
        raise ValueError("Invalid package metadata")
    if not _text(package.get("title"), "title").startswith("Mercado minorista de electricidad"):
        raise ValueError("Package is not the electricity market dataset")
    period = _text(_extra(package, "periodo"), "periodo")
    if not PERIOD.fullmatch(period):
        raise ValueError(f"Invalid quarter: {period}")
    if package.get("license_id") != "CC-BY-SA-4.0":
        raise ValueError(f"Unexpected license for {period}")
    resources = [r for r in package.get("resources", []) if r.get("position") == 0 and r.get("datastore_active")]
    if len(resources) != 1:
        raise ValueError(f"Expected one active datastore resource for {period}")
    return (
        period,
        _text(package.get("name"), "package name"),
        _text(resources[0].get("id"), "resource id"),
        _text(package.get("metadata_modified"), "metadata_modified"),
    )


def _fetch(action: str, params: dict[str, Any], *, max_bytes: int = 20_000_000) -> dict[str, Any]:
    url = f"{API}/{action}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status != 200 or "json" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError(f"Unexpected response for {action}")
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isdecimal() or int(length) > max_bytes):
                    raise ValueError(f"Oversized response for {action}")
                body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ValueError(f"Oversized response for {action}")
            prefix = body.lstrip()
            if prefix.startswith(b"\xef\xbb\xbf"):
                prefix = prefix[3:].lstrip()
            if not prefix.startswith(b"{"):
                raise ValueError(f"Not a JSON object response for {action}")
            try:
                data = json.loads(body.decode("utf-8-sig"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise ValueError(f"Invalid JSON response for {action}") from error
            if (
                not isinstance(data, dict)
                or data.get("success") is not True
                or not isinstance(data.get("result"), dict)
            ):
                raise ValueError(f"Invalid CKAN response for {action}")
            time.sleep(1)
            return data["result"]
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(5 * 2**attempt)
    raise AssertionError("unreachable")


def discover() -> dict[str, dict[str, Any]]:
    """Discover published electricity quarters without guessing package names."""
    found: dict[str, dict[str, Any]] = {}
    start = 0
    while True:
        page = _fetch(
            "package_search",
            {
                "fq": 'tags:"mercado minorista" AND extras_estado:publicado',
                "rows": 100,
                "start": start,
            },
        )
        results, count = page.get("results"), page.get("count")
        if (
            not isinstance(results, list)
            or len(results) > 100
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
            or count > 10_000
            or start + len(results) > count
        ):
            raise ValueError("Invalid package search page")
        for package in results:
            if not isinstance(package, dict) or not str(package.get("title", "")).startswith(
                "Mercado minorista de electricidad"
            ):
                continue
            period = package_metadata(package)[0]
            if period in found:
                raise ValueError(f"Duplicate package for {period}")
            found[period] = package
        start += len(results)
        if start >= count:
            return dict(sorted(found.items()))
        if not results:
            raise ValueError("Package search stopped before reported count")


def online_rows(resource_id: str) -> Iterator[dict[str, Any]]:
    """Read all rows in stable source-id order, checking each page's declared total."""
    offset, total = 0, None
    while total is None or offset < total:
        page = _fetch(
            "datastore_search",
            {
                "resource_id": resource_id,
                "limit": 10_000,
                "offset": offset,
                "sort": "_id asc",
            },
        )
        records, page_total = page.get("records"), page.get("total")
        if (
            not isinstance(records, list)
            or len(records) > 10_000
            or not isinstance(page_total, int)
            or isinstance(page_total, bool)
            or not 0 <= page_total <= 100_000
        ):
            raise ValueError("Invalid datastore page")
        if total is not None and page_total != total:
            raise ValueError("Datastore total changed during download")
        total = page_total
        if not records and offset < total:
            raise ValueError("Datastore ended before declared total")
        if offset + len(records) > total:
            raise ValueError("Datastore exceeded declared total")
        yield from records
        offset += len(records)
    if offset != total:
        raise ValueError("Datastore returned an inconsistent row count")


def cached_quarters(root: Path) -> dict[str, dict[str, Any]]:
    """Use the verified Phase 0 cache without copying it into this worktree."""
    found = {}
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not PERIOD.fullmatch(folder.name):
            continue
        package = _read_json(folder / "metadatos.json", 2_000_000)
        if package_metadata(package)[0] != folder.name:
            raise ValueError(f"Quarter mismatch in {folder}")
        found[folder.name] = package
    return found


def cached_rows(root: Path, period: str) -> Iterator[dict[str, Any]]:
    rows = _read_json(root / period / "via_api.json", 150_000_000)
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise ValueError(f"Invalid cached rows for {period}")
    yield from rows


def _row(raw: Any, period: str) -> tuple[tuple[Any, ...], list[tuple[str, str, str, str, int]], list[tuple[str, str]]]:
    if not isinstance(raw, dict) or not REQUIRED <= raw.keys():
        raise ValueError(f"Missing source columns in {period}")
    source_id = _integer(raw["_id"], "_id")
    if _text(raw["fecha"], "fecha") != period:
        raise ValueError(f"Row {source_id} has wrong quarter")
    distributor_code = _text(raw["cod_dis"], "cod_dis")
    if not DISTRIBUTOR.fullmatch(distributor_code):
        raise ValueError(f"Unknown distributor code at row {source_id}")
    distributor_name, distributor_extinct = _name(raw["descripcion_distribuidor"], "descripcion_distribuidor")
    code = _text(raw["cod_com"], "cod_com")
    description, marketer_extinct = _name(raw["descripcion_comercializador"], "descripcion_comercializador")
    issues = []
    names = [("distributor", distributor_code, distributor_name, period, int(distributor_extinct))]
    if code in DIRECT_CODES:
        category, marketer_code, marketer_name = "direct_consumer", None, None
        if description != "Consumidor Directo":
            issues.append(("direct_consumer_description", description))
    elif code == "No Disponible":
        category, marketer_code, marketer_name = "unavailable", None, None
        if description != "No Disponible":
            issues.append(("unavailable_description", description))
    elif MARKETER.fullmatch(code):
        category, marketer_code = "marketer", code
        marketer_name = None if description == "Consumidor Directo" else description
        if marketer_name is None:
            issues.append(("marketer_code_direct_description", description))
        else:
            names.append(("marketer", code, marketer_name, period, int(marketer_extinct)))
    else:
        raise ValueError(f"Unknown marketer code {code!r} at row {source_id}")
    tariff = _text(raw["tarifa_acceso"], "tarifa_acceso")
    community = _text(raw["ccaa"], "ccaa")
    if community not in COMMUNITIES:
        raise ValueError(f"Unknown community {community!r} at row {source_id}")
    energy = _integer(raw["energia"], "energia", signed=True)
    if energy < 0:
        issues.append(("negative_energy", str(energy)))
    row = (
        "electricity",
        period,
        source_id,
        distributor_code,
        distributor_name,
        marketer_code,
        marketer_name,
        category,
        tariff,
        COMMUNITIES[community],
        _integer(raw["numero_suministro"], "numero_suministro"),
        energy,
    )
    return row, names, issues


def import_quarter(
    connection: sqlite3.Connection,
    package: dict[str, Any],
    rows: Iterator[dict[str, Any]],
    *,
    force: bool = False,
) -> tuple[str, int, bool]:
    """Replace one quarter atomically; source row IDs retain repeated business keys."""
    period, package_name, resource_id, modified = package_metadata(package)
    if not force:
        previous = connection.execute(
            "SELECT package_name, resource_id, metadata_modified FROM loads_view WHERE sector=? AND period=?",
            ("electricity", period),
        ).fetchone()
        if previous == (package_name, resource_id, modified):
            return period, 0, False

    parsed = []
    names = set()
    issues = []
    keys: dict[tuple[str, str, str, str], tuple[int, str]] = {}
    seen_ids = set()
    tariffs = set()
    for raw in rows:
        row, row_names, row_issues = _row(raw, period)
        source_id = row[2]
        if source_id in seen_ids:
            raise ValueError(f"Repeated source row id {source_id} in {period}")
        seen_ids.add(source_id)
        parsed.append(row)
        names.update(row_names)
        tariffs.add(row[8])
        for kind, detail in row_issues:
            issues.append(("electricity", period, source_id, kind, detail))
        key = (row[3], raw["cod_com"], row[8], row[9])
        signature = json.dumps({field: value for field, value in raw.items() if field != "_id"}, sort_keys=True)
        prior = keys.get(key)
        if prior is None:
            keys[key] = (source_id, signature)
        else:
            first_id, first_values = prior
            kind = "repeated_identical_key" if first_values == signature else "repeated_conflicting_key"
            detail = json.dumps({"first_source_id": first_id, "key": key}, ensure_ascii=False)
            issues.append(("electricity", period, source_id, kind, detail))
    if not parsed or len(parsed) > 100_000:
        raise ValueError(f"Invalid row count for {period}")
    # The literal list comes from the independently verified 2011-2025 profile. New values require review.
    known_tariffs = {
        "2.0 DHS",
        "2.0A",
        "2.0DHA",
        "2.0DHS",
        "2.0NA-DHA",
        "2.0TD",
        "2.1A",
        "2.1DHA",
        "2.1DHS",
        "3.0",
        "3.0A",
        "3.0TD/3.0TDVE",
        "3.0TD/TDVE",
        "3.1",
        "3.1A",
        "6.X",
        "6.xTD/6.1TDVE",
        "6.xTD/TDVE",
        "TRASVASES",
    }
    if tariffs - known_tariffs:
        raise ValueError(f"Unknown tariffs in {period}: {sorted(tariffs - known_tariffs)}")

    with connection:
        market_store.write_quarter(
            connection,
            (
                "electricity",
                period,
                package_name,
                resource_id,
                modified,
                len(parsed),
                datetime.now(UTC).isoformat(),
                SOURCE_URL,
                package["license_id"],
                _text(package.get("license_url"), "license_url"),
                CONDITIONS_URL,
                ATTRIBUTION,
            ),
            parsed,
            (
                ("electricity", observed_period, role, code, name, extinct)
                for role, code, name, observed_period, extinct in names
            ),
            issues,
        )
    return period, len(parsed), True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Local SQLite output path")
    parser.add_argument("--cache-root", type=Path, help="Verified Phase 0 raw data directory; omit for live CNMC API")
    parser.add_argument("--period", action="append", help="Only import this quarter; repeat for several")
    parser.add_argument("--force", action="store_true", help="Reimport even when metadata is unchanged")
    args = parser.parse_args()
    packages = cached_quarters(args.cache_root) if args.cache_root else discover()
    selected = args.period or list(packages)
    unknown = set(selected) - packages.keys()
    if unknown:
        parser.error(f"Unknown or unpublished quarters: {', '.join(sorted(unknown))}")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.database) as connection:
        market_store.initialize(connection)
        for period in selected:
            resource_id = package_metadata(packages[period])[2]
            rows = cached_rows(args.cache_root, period) if args.cache_root else online_rows(resource_id)
            _, count, changed = import_quarter(connection, packages[period], rows, force=args.force)
            print(f"{period}: {'imported ' + str(count) + ' rows' if changed else 'unchanged'}")


if __name__ == "__main__":
    main()

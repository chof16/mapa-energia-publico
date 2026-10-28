"""Validate the reviewed CNMC gas-network annex before any persistent writes."""

import argparse
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from electricity_map_ingestion import gas_distribution_store
from electricity_map_ingestion.cnmc_client import download_document

SOURCE_URL = "https://www.cnmc.es/expedientes/isde00720-0"
DOWNLOAD_URL = "https://www.cnmc.es/sites/default/files/3085926.xlsx"
SOURCE_SHA256 = "d9ea1fc4783c916a849c88271831cac41ab9ea192e274207ff56d9df99e3b87d"
PERIOD = "2019-06"
PUBLISHED_ON = "2020-07-29"
TITLE = "Municipios con redes de distribución de gas de presión menor o igual a 4 bar (junio de 2019)"
MAX_BYTES = 2_000_000
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# Exact province subtotal labels in this annex, joined to official two-digit INE codes.
PROVINCES = {
    "ARABA/ÁLAVA": "01",
    "ALBACETE": "02",
    "ALICANTE/ALACANT": "03",
    "ALMERÍA": "04",
    "AVILA": "05",
    "BADAJOZ": "06",
    "BALEARES": "07",
    "BARCELONA": "08",
    "BURGOS": "09",
    "CACERES": "10",
    "CÁDIZ": "11",
    "CASTELLÓN/CASTELLÓ": "12",
    "CIUDAD REAL": "13",
    "CÓRDOBA": "14",
    "CORUÑA, A": "15",
    "CUENCA": "16",
    "GIRONA": "17",
    "GRANADA": "18",
    "GUADALAJARA": "19",
    "GIPUZKOA": "20",
    "HUELVA": "21",
    "HUESCA": "22",
    "JAEN": "23",
    "LEON": "24",
    "LLEIDA": "25",
    "RIOJA, LA": "26",
    "LUGO": "27",
    "MADRID": "28",
    "MÁLAGA": "29",
    "MURCIA": "30",
    "NAVARRA": "31",
    "OURENSE": "32",
    "ASTURIAS": "33",
    "PALENCIA": "34",
    "PONTEVEDRA": "36",
    "SALAMANCA": "37",
    "CANTABRIA": "39",
    "SEGOVIA": "40",
    "SEVILLA": "41",
    "SORIA": "42",
    "TARRAGONA": "43",
    "TERUEL": "44",
    "TOLEDO": "45",
    "VALENCIA/VALÈNCIA": "46",
    "VALLADOLID": "47",
    "BIZKAIA": "48",
    "ZAMORA": "49",
    "ZARAGOZA": "50",
}
REGIONS = {
    "ANDALUCÍA": "04 11 14 18 21 23 29 41",
    "ARAGÓN": "22 44 50",
    "CASTILLA LA MANCHA": "02 13 16 19 45",
    "CASTILLA Y  LEÓN": "05 09 24 34 37 40 42 47 49",
    "CATALUÑA": "08 17 25 43",
    "COMUNIDAD VALENCIANA": "03 12 46",
    "EXTREMADURA": "06 10",
    "GALICIA": "15 27 32 36",
    "PAÍS VASCO": "01 20 48",
}


@dataclass(frozen=True)
class NetworkRow:
    source_row_id: int
    province_code: str
    municipality_name: str
    distributor_name: str
    supply_points: int


def _xml(archive: zipfile.ZipFile, name: str) -> ElementTree.Element:
    raw = archive.read(name)
    if b"\x00" in raw or b"<!doctype" in raw.lower() or b"<!entity" in raw.lower():
        raise ValueError("Unsafe annex XML")
    text = raw.decode("utf-8-sig")
    if not text.lstrip().startswith("<?xml"):
        raise ValueError("Unexpected annex XML encoding or signature")
    root = ElementTree.fromstring(text)
    if sum(1 for _ in root.iter()) > 60_000:
        raise ValueError("Annex XML element limit exceeded")
    return root


def _cells(body: bytes) -> list[tuple[int, dict[str, str]]]:
    if not 0 < len(body) <= MAX_BYTES or not body.startswith(b"PK\x03\x04"):
        raise ValueError("Invalid annex size or XLSX signature")
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            required = {"[Content_Types].xml", "xl/workbook.xml", "xl/sharedStrings.xml", "xl/worksheets/sheet1.xml"}
            if (
                not required.issubset(names)
                or len(entries) > 32
                or len(set(names)) != len(names)
                or sum(entry.file_size for entry in entries) > 4_000_000
                or any(
                    entry.file_size > 2_000_000
                    or entry.flag_bits & 1
                    or entry.compress_type not in (0, 8)
                    or entry.filename.startswith("/")
                    or ".." in entry.filename.split("/")
                    or entry.file_size > max(1, entry.compress_size) * 200
                    for entry in entries
                )
                or any("vba" in name.lower() or "externallinks" in name.lower() for name in names)
            ):
                raise ValueError("Unsupported or oversized annex archive")
            workbook = _xml(archive, "xl/workbook.xml")
            sheets = workbook.findall("m:sheets/m:sheet", NS)
            if len(sheets) != 1 or sheets[0].get("name") != "Municipios gas natural <=4bar 2":
                raise ValueError("Unexpected annex worksheet")
            shared = _xml(archive, "xl/sharedStrings.xml")
            strings = ["".join(element.itertext()) for element in shared]
            if len(strings) > 5_000 or any(len(value) > 300 for value in strings):
                raise ValueError("Annex text limits exceeded")
            worksheet = _xml(archive, "xl/worksheets/sheet1.xml")
            dimension = worksheet.find("m:dimension", NS)
            if dimension is None or not re.fullmatch(r"[A-E][1-9]\d{0,3}:[A-E][1-9]\d{0,3}", dimension.get("ref", "")):
                raise ValueError("Invalid annex dimensions")
            rows = worksheet.findall("m:sheetData/m:row", NS)
            if not 4 <= len(rows) <= 3_000:
                raise ValueError("Annex row limit exceeded")
            result = []
            previous = 0
            for row in rows:
                row_id = int(row.attrib["r"])
                if not previous < row_id <= 3_000 or len(row) > 5:
                    raise ValueError("Invalid annex row width or order")
                previous = row_id
                cells = {}
                for cell in row:
                    ref = cell.get("r", "")
                    if not re.fullmatch(r"[A-E]" + str(row_id), ref) or cell.find("m:f", NS) is not None:
                        raise ValueError("Invalid annex cell or formula")
                    value = cell.find("m:v", NS)
                    if value is None:
                        if cell.find("m:is", NS) is not None:
                            raise ValueError("Unexpected inline annex text")
                        continue
                    if ref[0] in cells or value.text is None or len(value.text) > 300:
                        raise ValueError("Invalid annex cell value")
                    if cell.get("t") == "s":
                        index = int(value.text)
                        if not 0 <= index < len(strings):
                            raise ValueError("Invalid annex shared string")
                        cells[ref[0]] = strings[index]
                    elif cell.get("t", "n") == "n":
                        cells[ref[0]] = value.text
                    else:
                        raise ValueError("Unsupported annex cell type")
                result.append((row_id, cells))
            return result
    except (zipfile.BadZipFile, KeyError, IndexError, UnicodeError, ElementTree.ParseError) as error:
        raise ValueError("Invalid gas-network XLSX annex") from error


def parse_annex(body: bytes) -> list[NetworkRow]:
    """Preserve source rows; use province subtotals, never fuzzy municipality joins."""
    cells = _cells(body)
    title = (
        "Relación de Municipios con redes de distribución de gas de presión menor o igual a 4 bar \n (junio de 2019)"
    )
    if cells[:2] != [(2, {"B": title}), (3, {"B": "Municipio", "C": "Distribuidora", "D": "Puntos de suministro"})]:
        raise ValueError("Unexpected annex title, reporting period or headers")
    result, pending, province_totals = [], [], {}
    national_total = None
    for row_id, values in cells[2:]:
        if national_total is not None or set(values) not in ({"B", "C", "D"}, {"B", "D"}):
            raise ValueError("Unexpected annex row shape")
        if not re.fullmatch(r"\d{1,9}", values["D"]):
            raise ValueError("Invalid or missing annex supply-point count")
        count = int(values["D"])
        label = values["B"]
        if "C" in values:
            if not label.strip() or not values["C"].strip() or max(len(label), len(values["C"])) > 160:
                raise ValueError("Invalid annex observation text")
            pending.append((row_id, label, values["C"], count))
        elif label.startswith("Total ") and label[6:] in PROVINCES:
            code = PROVINCES[label[6:]]
            if not pending or code in province_totals or sum(row[3] for row in pending) != count:
                raise ValueError("Annex province subtotal mismatch")
            result.extend(NetworkRow(row, code, name, company, points) for row, name, company, points in pending)
            pending = []
            province_totals[code] = count
        elif label.startswith("Total ") and label[6:] in REGIONS:
            codes = REGIONS[label[6:]].split()
            if (
                pending
                or any(code not in province_totals for code in codes)
                or sum(province_totals[c] for c in codes) != count
            ):
                raise ValueError("Annex regional subtotal mismatch")
        elif label == "TOTAL ESPAÑA":
            if pending or sum(province_totals.values()) != count:
                raise ValueError("Annex national subtotal mismatch")
            national_total = count
        else:
            raise ValueError("Unreviewed annex territorial subtotal")
    if national_total is None or pending or not result:
        raise ValueError("Incomplete annex")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the reviewed June 2019 gas-network annex locally")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--archive", type=Path, default=Path("datos/raw/gas-distribution"))
    args = parser.parse_args()
    if args.xlsx:
        if args.xlsx.stat().st_size > MAX_BYTES:
            raise ValueError("Annex exceeds byte limit")
        with args.xlsx.open("rb") as handle:
            body = handle.read(MAX_BYTES + 1)
    else:
        cached = args.archive / "cnmc-gas-networks-2019-06.xlsx"
        if cached.exists():
            with cached.open("rb") as handle:
                body = handle.read(MAX_BYTES + 1)
        else:
            body = download_document(DOWNLOAD_URL, max_bytes=MAX_BYTES)
    if hashlib.sha256(body).hexdigest() != SOURCE_SHA256:
        raise ValueError("Annex revision is unreviewed; verify the source before importing")
    rows = parse_annex(body)
    if (
        len(rows) != 1993
        or len({row.province_code for row in rows}) != 48
        or sum(row.supply_points for row in rows) != 7957923
    ):
        raise ValueError("Reviewed annex counts changed")
    # The reviewed source contains statistical company observations, no census contacts.
    if not args.xlsx:
        args.archive.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(body)
    args.database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        gas_distribution_store.initialize(connection)
        load_id = gas_distribution_store.write_load(connection, rows, SOURCE_SHA256)
    print(json.dumps({"load_id": load_id, "period": PERIOD, "rows": len(rows), "provinces": 48}))


if __name__ == "__main__":
    main()

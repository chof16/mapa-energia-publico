"""Shared CNMC Data transport, pagination and scalar validation for energy ingestion."""

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Any

API = "https://catalogodatos.cnmc.es/api/3/action"
CONDITIONS_URL = "https://data.cnmc.es/condiciones-de-uso"
ATTRIBUTION = "Origen de los datos: Comisión Nacional de los Mercados y la Competencia"
USER_AGENT = "mapa-energia-es/0.1 (proyecto no comercial; datos abiertos CNMC)"


def text_value(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def integer_value(value: Any, field: str, *, signed: bool = False) -> int:
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


def extra_value(package: dict[str, Any], key: str) -> Any:
    return next((item.get("value") for item in package.get("extras", []) if item.get("key") == key), None)


def fetch(action: str, params: dict[str, Any], *, max_bytes: int = 20_000_000) -> dict[str, Any]:
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


def download_document(url: str, *, max_bytes: int) -> bytes:
    """Bounded transport for reviewed CNMC documents; their terms are independent of Data."""
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.cnmc.es"
        or not parsed.path.startswith("/sites/default/files/")
    ):
        raise ValueError("Unexpected CNMC document URL")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        length = response.headers.get("Content-Length")
        if response.status != 200 or (length and (not length.isdecimal() or int(length) > max_bytes)):
            raise ValueError("Invalid CNMC document response")
        body = response.read(max_bytes + 1)
    time.sleep(1)
    if len(body) > max_bytes:
        raise ValueError("CNMC document exceeds byte limit")
    return body


def online_rows(resource_id: str) -> Iterator[dict[str, Any]]:
    """Read all rows in stable source-id order, checking each page's declared total."""
    offset, total = 0, None
    while total is None or offset < total:
        page = fetch(
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

"""Reconcile a local network import and every provincial API page against the reviewed annex."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from electricity_map_api.config import Settings
from electricity_map_api.main import create_app
from electricity_map_ingestion.gas_distribution import MAX_BYTES, SOURCE_SHA256, parse_annex
from fastapi.testclient import TestClient


def verify(database: Path, annex: Path) -> dict[str, object]:
    with annex.open("rb") as handle:
        body = handle.read(MAX_BYTES + 1)
    if hashlib.sha256(body).hexdigest() != SOURCE_SHA256:
        raise ValueError("Unreviewed annex revision")
    expected = parse_annex(body)
    with sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True) as connection:
        actual = connection.execute(
            "SELECT source_row_id, province_code, municipality_name, distributor_name, supply_points "
            "FROM gas_network_rows WHERE load_id=? ORDER BY source_row_id",
            (SOURCE_SHA256,),
        ).fetchall()
        assert actual == [
            (r.source_row_id, r.province_code, r.municipality_name, r.distributor_name, r.supply_points)
            for r in expected
        ]
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
    provinces = sorted({row.province_code for row in expected})
    with TestClient(create_app(Settings(database=database, development_mode=True))) as client:
        base = "/v1/gas/distribution"
        items = []
        for offset in range(0, len(provinces), 7):
            response = client.get(base + "/provinces", params={"limit": 7, "offset": offset, "load_id": SOURCE_SHA256})
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == len(provinces) and data["source"]["period"] == "2019-06"
            items.extend(data["items"])
        assert [row["province_code"] for row in items] == provinces
        for province in items:
            rows = [row for row in expected if row.province_code == province["province_code"]]
            counts = Counter(row.distributor_name for row in rows)
            assert province["documented_distributor_count"] == len(counts)
            assert province["source_row_count"] == len(rows)
            assert province["supply_points"] == sum(row.supply_points for row in rows)
            response = client.get(
                base + "/provinces/" + province["province_code"], params={"load_id": SOURCE_SHA256, "limit": 100}
            )
            assert response.status_code == 200
            detail = response.json()
            assert detail["total"] == len(counts) and detail["complete"] is False
            assert detail["items"] == [
                {
                    "distributor_name": name,
                    "source_row_count": counts[name],
                    "supply_points": sum(row.supply_points for row in rows if row.distributor_name == name),
                }
                for name in sorted(counts)
            ]
        for code in ("35", "38", "51", "52"):
            data = client.get(base + "/provinces/" + code).json()
            assert data["items"] == [] and data["complete"] is False
    return {
        "period": "2019-06",
        "source_rows": len(expected),
        "provinces": len(provinces),
        "observed_distributor_names": len({row.distributor_name for row in expected}),
        "supply_points": sum(row.supply_points for row in expected),
        "source_sha256": SOURCE_SHA256,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--xlsx", type=Path, default=Path("datos/raw/gas-distribution/cnmc-gas-networks-2019-06.xlsx"))
    args = parser.parse_args()
    print(json.dumps(verify(args.database, args.xlsx)))


if __name__ == "__main__":
    main()

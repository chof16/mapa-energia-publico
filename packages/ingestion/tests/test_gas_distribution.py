"""Synthetic annex validation: no downloaded rows or personal records in fixtures."""

import io
import sqlite3
import zipfile
from xml.sax.saxutils import escape

import pytest
from electricity_map_ingestion import gas_distribution as ingestion
from electricity_map_ingestion import gas_distribution_store as store

from scripts.export_database import _ordered_dump


def annex(*, count="10", subtotal="20", header="Municipio", extra=None):
    strings = [
        "Relación de Municipios con redes de distribución de gas de presión menor o igual a 4 bar \n (junio de 2019)",
        header,
        "Distribuidora",
        "Puntos de suministro",
        "Municipio sintético",
        "Empresa sintética SA",
        "Total MADRID",
        "TOTAL ESPAÑA",
    ]
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rows = (
        '<row r="2"><c r="B2" t="s"><v>0</v></c></row>'
        '<row r="3"><c r="B3" t="s"><v>1</v></c><c r="C3" t="s"><v>2</v></c><c r="D3" t="s"><v>3</v></c></row>'
        + "".join(
            f'<row r="{n}"><c r="B{n}" t="s"><v>4</v></c><c r="C{n}" t="s"><v>5</v></c>'
            f'<c r="D{n}"><v>{count}</v></c></row>'
            for n in (4, 5)
        )
        + f'<row r="6"><c r="B6" t="s"><v>6</v></c><c r="D6"><v>{subtotal}</v></c></row>'
        + f'<row r="7"><c r="B7" t="s"><v>7</v></c><c r="D7"><v>{subtotal}</v></c></row>'
    )
    members = {
        "[Content_Types].xml": '<?xml version="1.0"?><Types/>',
        "xl/workbook.xml": f'<?xml version="1.0"?><workbook xmlns="{namespace}"><sheets>'
        '<sheet name="Municipios gas natural &lt;=4bar 2"/></sheets></workbook>',
        "xl/sharedStrings.xml": f'<?xml version="1.0"?><sst xmlns="{namespace}">'
        + "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
        + "</sst>",
        "xl/worksheets/sheet1.xml": f'<?xml version="1.0"?><worksheet xmlns="{namespace}">'
        f'<dimension ref="B2:D7"/><sheetData>{rows}</sheetData></worksheet>',
    }
    members.update(extra or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return stream.getvalue()


def test_exact_subtotals_source_rows_and_zero():
    rows = ingestion.parse_annex(annex())
    assert [(row.source_row_id, row.province_code, row.supply_points) for row in rows] == [(4, "28", 10), (5, "28", 10)]
    assert len(ingestion.parse_annex(annex(count="0", subtotal="0"))) == 2


@pytest.mark.parametrize(
    "body",
    [
        b"<html>not xlsx</html>",
        b"PK\x03\x04invalid",
        b"x" * (ingestion.MAX_BYTES + 1),
        annex(count=""),
        annex(count="1.5"),
        annex(count="-1"),
        annex(subtotal="19"),
        annex(header="Contact address"),
        annex(extra={"xl/vbaProject.bin": "macro"}),
        annex(extra={"../escape": "value"}),
        annex(extra={"huge": "a" * 2_000_001}),
        annex(
            extra={
                "xl/sharedStrings.xml": '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x/>'
            }
        ),
        annex(
            extra={
                "xl/worksheets/sheet1.xml": (
                    '<?xml version="1.0"?><worksheet><dimension ref="A1:XFD1048576"/></worksheet>'
                )
            }
        ),
    ],
)
def test_rejects_unvalidated_content(body):
    with pytest.raises(ValueError):
        ingestion.parse_annex(body)


def test_unreviewed_input_cannot_create_database_or_archive(tmp_path, monkeypatch, capsys):
    path = tmp_path / "unreviewed.xlsx"
    path.write_bytes(annex(header="PRIVATE SENTINEL"))
    database = tmp_path / "not-created.sqlite"
    archive = tmp_path / "not-created-archive"
    monkeypatch.setattr(
        "sys.argv",
        ["ingest-gas-distribution", "--database", str(database), "--xlsx", str(path), "--archive", str(archive)],
    )
    with pytest.raises(ValueError, match="unreviewed") as error:
        ingestion.main()
    assert "PRIVATE SENTINEL" not in str(error.value) + str(capsys.readouterr())
    assert not database.exists() and not archive.exists()


def test_history_duplicates_rollback_and_export():
    rows = ingestion.parse_annex(annex())
    with sqlite3.connect(":memory:") as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("CREATE TABLE electricity_sentinel (value INTEGER)")
        connection.execute("INSERT INTO electricity_sentinel VALUES (7)")
        store.initialize(connection)
        store.write_load(connection, rows, "a" * 64)
        store.write_load(connection, rows, "a" * 64)
        store.write_load(connection, rows, "b" * 64)
        connection.commit()
        assert connection.execute("SELECT count(*) FROM gas_network_rows").fetchone() == (4,)
        with pytest.raises(RuntimeError), connection:
            store.write_load(connection, rows, "c" * 64)
            raise RuntimeError("Synthetic rollback")
        assert connection.execute("SELECT count(*) FROM gas_network_loads").fetchone() == (2,)
        dump = "\n".join(_ordered_dump(connection))
    with sqlite3.connect(":memory:") as replay:
        replay.execute("PRAGMA foreign_keys=ON")
        replay.executescript(dump)
        assert replay.execute("SELECT value FROM electricity_sentinel").fetchone() == (7,)
        assert replay.execute("SELECT count(*) FROM gas_network_rows").fetchone() == (4,)
        assert replay.execute("PRAGMA foreign_key_check").fetchone() is None

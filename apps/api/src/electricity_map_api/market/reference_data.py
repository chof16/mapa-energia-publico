"""Reviewed electricity COR list, independent of distributor coverage."""

from datetime import date

from electricity_map_domain import EnergySector

from electricity_map_api.market.schemas import ReferenceMarketer, ReferenceMarketersResponse

SNAPSHOT_DATE = date(2026, 10, 4)
DESIGNATION_SOURCE_URL = "https://www.cnmc.es/facil-para-ti/que-hace-la-cnmc-para-consumidores/bono-social-electrico"
CODE_SOURCE_URL = "https://data.cnmc.es/energia/energia-electrica/energia-y-suministros"
CODE_SOURCE_PERIOD = "2025T4"
CODE_SOURCE_METADATA_MODIFIED = "2026-09-16T09:54:27.287603"
ATTRIBUTION = "Origen de los datos: Comisión Nacional de los Mercados y la Competencia"

# The CNMC lists these eight electricity CORs. R2 codes were matched to their
# names in the 2025T4 CNMC Data load. Only Ceuta and Melilla have a territorial
# restriction stated by the CNMC; None does not assert exclusive national reach.
REFERENCE_MARKETERS: tuple[tuple[str, str, str | None], ...] = (
    ("R2-292", "ENERGÍA XXI COMERCIALIZADORA DE REFERENCIA, S.L.", None),
    ("R2-329", "CURENERGÍA COMERCIALIZADOR DE ÚLTIMO RECURSO S.A.U.", None),
    ("R2-356", "COMERCIALIZADORA REGULADA GAS & POWER, S.A.", None),
    ("R2-284", "BASER COMERCIALIZADORA DE REFERENCIA, S.A.", None),
    ("R2-290", "RÉGSITI COMERCIALIZADORA REGULADA, S.L.U.", None),
    ("R2-540", "COMERCIALIZADOR DE REFERENCIA ENERGÉTICO, S.L.U.", None),
    ("R2-532", "TERAMELCOR, S.L.", "melilla"),
    ("R2-530", "ENERGÍA CEUTA XXI COMERCIALIZADORA DE REFERENCIA S.A.", "ceuta"),
)


def reference_marketers(sector: EnergySector) -> ReferenceMarketersResponse:
    """Return reviewed COR status without pairing it to a distributor."""
    available = sector == EnergySector.ELECTRICITY
    return ReferenceMarketersResponse(
        sector=sector,
        snapshot_date=SNAPSHOT_DATE,
        scope="reference_marketers",
        designation_source_url=DESIGNATION_SOURCE_URL if available else None,
        code_source_url=CODE_SOURCE_URL if available else None,
        code_source_period=CODE_SOURCE_PERIOD if available else None,
        code_source_metadata_modified=CODE_SOURCE_METADATA_MODIFIED if available else None,
        attribution=ATTRIBUTION if available else None,
        items=(
            [
                ReferenceMarketer(marketer_code=code, name=name, territorial_limit=limit)
                for code, name, limit in REFERENCE_MARKETERS
            ]
            if available
            else []
        ),
    )

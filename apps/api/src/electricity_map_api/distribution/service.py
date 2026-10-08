"""Read only accepted provincial claims from the distribution snapshot."""

import json
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from electricity_map_api.distribution.models import (
    ClaimDecision,
    DistributionSnapshot,
    DistributorIdentity,
    GroupAssociation,
)
from electricity_map_api.distribution.schemas import (
    AssociationEvidence,
    CorporateGroupAssociation,
    CoverageEvidence,
    DistributorPresence,
    ProvincePresenceSummaryItem,
)


def snapshot_date(session: Session) -> date:
    value = session.scalars(select(DistributionSnapshot.snapshot_date).where(DistributionSnapshot.id == 1)).one()
    return date.fromisoformat(value)


def documented_provinces(session: Session) -> list[ProvincePresenceSummaryItem]:
    rows = session.execute(
        select(ClaimDecision.province_code, func.count().label("documented_distributor_count"))
        .where(ClaimDecision.status == "accepted")
        .group_by(ClaimDecision.province_code)
        .order_by(ClaimDecision.province_code)
    ).mappings()
    return [ProvincePresenceSummaryItem(**row) for row in rows]


def presence_for_province(session: Session, province_code: str) -> list[DistributorPresence]:
    rows = session.execute(
        select(
            DistributorIdentity.code,
            DistributorIdentity.name,
            DistributorIdentity.registry_source_url,
            ClaimDecision.evidence_json,
            GroupAssociation.group_name,
            GroupAssociation.evidence_json.label("group_evidence_json"),
        )
        .select_from(ClaimDecision)
        .join(DistributorIdentity, DistributorIdentity.code == ClaimDecision.distributor_code)
        .outerjoin(GroupAssociation, GroupAssociation.distributor_code == DistributorIdentity.code)
        .where(ClaimDecision.status == "accepted", ClaimDecision.province_code == province_code)
        .order_by(ClaimDecision.id)
    )
    items = []
    for row in rows:
        group = (
            CorporateGroupAssociation(
                group_name=row.group_name,
                evidence=AssociationEvidence.model_validate(json.loads(row.group_evidence_json)),
            )
            if row.group_name
            else None
        )
        items.append(
            DistributorPresence(
                distributor_code=row.code,
                distributor_name=row.name,
                registry_source_url=row.registry_source_url,
                evidence=CoverageEvidence.model_validate(json.loads(row.evidence_json)),
                cor=None,
                corporate_group=group,
            )
        )
    return items

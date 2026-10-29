"""Apply explicit company identities across reports without changing source observations."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from electricity_map_ingestion.gas_retail import Contract, Entity, Evidence, Identifier, read_json_object
from electricity_map_ingestion.gas_retail_store import revision_id


class Reference(Contract):
    source_id: Identifier
    page: Annotated[int, Field(ge=1, le=200)]


class IdentityDecision(Contract):
    entity: Entity
    mapping_ids: Annotated[list[Identifier], Field(min_length=1, max_length=20_000)]
    references: Annotated[list[Reference], Field(min_length=1, max_length=200)]


class IdentityRegistry(Contract):
    version: Literal[1]
    base_load_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    decisions: Annotated[list[IdentityDecision], Field(min_length=1, max_length=20_000)]


def read_registry(path: Path) -> IdentityRegistry:
    return IdentityRegistry.model_validate(read_json_object(path))


def reconcile(evidence: Evidence, registry: IdentityRegistry) -> Evidence:
    """Keep company identity independent from the source-specific observed name, as for electricity."""
    if registry.base_load_id != revision_id(evidence):
        raise ValueError("Identity review belongs to another evidence revision")
    sources = {source.source_id: source for source in evidence.sources}
    entities = {entity.gas_id: entity for entity in evidence.entities}
    mappings = {mapping.mapping_id: mapping for mapping in evidence.mappings}
    decisions = {}
    canonical = {}
    for decision in registry.decisions:
        entity = decision.entity
        if evidence.version == 2 and not entity.review_note.startswith("reviewed_identity:"):
            raise ValueError("Canonical identity decision requires explicit reviewed_identity admission")
        if entity.gas_id in canonical:
            raise ValueError("Duplicate canonical company identity")
        canonical[entity.gas_id] = entity
        for reference in decision.references:
            if reference.source_id not in sources or reference.page > sources[reference.source_id].page_count:
                raise ValueError("Identity reference outside source")
        for mapping_id in decision.mapping_ids:
            if mapping_id not in mappings or mapping_id in decisions:
                raise ValueError("Unknown or repeated identity mapping")
            if entities[mappings[mapping_id].gas_id].kind != entity.kind:
                raise ValueError("Cannot merge retailer, group, rest or total identities")
            decisions[mapping_id] = decision
    if set(decisions) != set(mappings):
        raise ValueError("Identity review must account for every observed mapping")
    # Reject a proposed merge of simultaneously reported companies. Existing repeated
    # source rows with the same mapping remain intact and retain aggregation safeguards.
    cells = defaultdict(set)
    for row in evidence.observations:
        entity = decisions[row.mapping_id].entity
        key = row.source_id, entity.gas_id, row.month, row.metric, row.scope
        cells[key].add(row.mapping_id)
    if any(len(ids) > 1 for ids in cells.values()):
        raise ValueError("Identity merge combines coexisting source rows")
    catalogue_ids = {entry.gas_id for entry in evidence.catalogue}
    if catalogue_ids & canonical.keys():
        raise ValueError("Statistical identities must remain independent from the CUR catalogue")
    data = evidence.model_dump()
    data["entities"] = [entity.model_dump() for entity in canonical.values()] + [
        entities[gas_id].model_dump() for gas_id in sorted(catalogue_ids)
    ]
    for row in data["mappings"]:
        decision = decisions[row["mapping_id"]]
        row["gas_id"] = decision.entity.gas_id
        refs = "; ".join(f"{ref.source_id} p.{ref.page}" for ref in decision.references[:5])
        row["review_note"] = f"{decision.entity.review_note} Referencias: {refs}."[:1000]
    if evidence.version == 2:
        for index, decision in enumerate(registry.decisions):
            data["review_records"].append(
                dict(
                    record_id=f"company-identity-{registry.base_load_id[:12]}-{index:04}",
                    category="identity_event",
                    payload_json=json.dumps(
                        dict(base_load_id=registry.base_load_id, decision=decision.model_dump()),
                        ensure_ascii=False,
                    ),
                )
            )
    return Evidence.model_validate(data)

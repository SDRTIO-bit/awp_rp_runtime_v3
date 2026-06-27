"""MemoryCurationEvidence — evidence supporting a memory curation candidate.

schemaId: awp.rp.memory-curation-evidence.v1

Every candidate must have at least one evidence reference from an accepted
turn. No evidence = candidate rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.memory-curation-evidence.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MemoryCurationEvidence:
    """Evidence binding a memory candidate to an accepted fact source."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    evidence_id: str = ""
    source_turn_id: str = ""
    source_card_state_revision: int = 0
    evidence_type: str = ""   # "accepted_turn", "card_state", "active_memory", "rag_memory"
    quote: str = ""           # short quote from the source (not full text)
    relevance: float = 0.5   # 0-1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "source_turn_id": self.source_turn_id,
            "source_card_state_revision": self.source_card_state_revision,
            "evidence_type": self.evidence_type,
            "quote": self.quote,
            "relevance": self.relevance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCurationEvidence:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            evidence_id=data.get("evidence_id", ""),
            source_turn_id=data.get("source_turn_id", ""),
            source_card_state_revision=data.get("source_card_state_revision", 0),
            evidence_type=data.get("evidence_type", ""),
            quote=data.get("quote", ""),
            relevance=data.get("relevance", 0.5),
        )

"""WorldLifeEvidence — evidence supporting a world-life candidate.

schemaId: awp.rp.world-life-evidence.v1
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.world-life-evidence.v1"
SCHEMA_VERSION = 1

@dataclass
class WorldLifeEvidence:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    evidence_id: str = ""
    source_type: str = ""  # accepted_turn, active_memory, rag_memory, worldbook, card_state
    source_ref: str = ""
    excerpt: str = ""
    entity_refs: list[str] = field(default_factory=list)
    location_ref: str = ""
    confidence: float = 0.5
    relevance_score: float = 0.5
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "evidence_id": self.evidence_id, "source_type": self.source_type,
            "source_ref": self.source_ref, "excerpt": self.excerpt,
            "entity_refs": self.entity_refs, "location_ref": self.location_ref,
            "confidence": self.confidence, "relevance_score": self.relevance_score,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldLifeEvidence:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            evidence_id=data.get("evidence_id", ""),
            source_type=data.get("source_type", ""),
            source_ref=data.get("source_ref", ""),
            excerpt=data.get("excerpt", ""),
            entity_refs=data.get("entity_refs", []),
            location_ref=data.get("location_ref", ""),
            confidence=data.get("confidence", 0.5),
            relevance_score=data.get("relevance_score", 0.5),
            created_at=data.get("created_at", ""),
        )

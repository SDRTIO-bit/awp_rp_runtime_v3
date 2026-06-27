"""ContinuityEvidence — evidence supporting a continuity issue.

schemaId: awp.rp.continuity-evidence.v1

Evidence priority (fixed):
  CardState > accepted_turn > ActiveMemory > high-confidence RagMemory
  > worldbook > AgentSuggestion > no-evidence speculation
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.continuity-evidence.v1"
SCHEMA_VERSION = 1


class EvidenceSourceType(str, Enum):
    CARD_STATE = "card_state"
    ACCEPTED_TURN = "accepted_turn"
    ACTIVE_MEMORY = "active_memory"
    RAG_MEMORY = "rag_memory"
    WORLDBOOK = "worldbook"
    DIRECTOR_PLAN = "director_plan"
    AGENT_SUGGESTION = "agent_suggestion"
    TOOL_RESULT = "tool_result"


class ConflictStatus(str, Enum):
    CONSISTENT = "consistent"
    STALE = "stale"
    CONFLICTED = "conflicted"


# Fixed evidence priority (higher = more authoritative)
EVIDENCE_PRIORITY: dict[EvidenceSourceType, int] = {
    EvidenceSourceType.CARD_STATE: 100,
    EvidenceSourceType.ACCEPTED_TURN: 90,
    EvidenceSourceType.ACTIVE_MEMORY: 80,
    EvidenceSourceType.RAG_MEMORY: 70,
    EvidenceSourceType.WORLDBOOK: 60,
    EvidenceSourceType.DIRECTOR_PLAN: 50,
    EvidenceSourceType.AGENT_SUGGESTION: 40,
    EvidenceSourceType.TOOL_RESULT: 30,
}


@dataclass
class ContinuityEvidence:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    evidence_id: str = ""
    source_type: EvidenceSourceType = EvidenceSourceType.TOOL_RESULT
    source_ref: str = ""
    source_turn_id: str = ""
    source_snapshot_id: str = ""
    source_card_state_revision: int = 0
    excerpt: str = ""
    entity_refs: list[str] = field(default_factory=list)
    location_refs: list[str] = field(default_factory=list)
    event_tags: list[str] = field(default_factory=list)
    confidence: float = 0.5
    recency: float = 0.5
    relevance_score: float = 0.5
    conflict_status: ConflictStatus = ConflictStatus.CONSISTENT
    created_at: str = ""

    @property
    def priority(self) -> int:
        """Fixed priority based on source type."""
        return EVIDENCE_PRIORITY.get(self.source_type, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "source_type": self.source_type.value,
            "source_ref": self.source_ref,
            "source_turn_id": self.source_turn_id,
            "source_snapshot_id": self.source_snapshot_id,
            "source_card_state_revision": self.source_card_state_revision,
            "excerpt": self.excerpt,
            "entity_refs": self.entity_refs,
            "location_refs": self.location_refs,
            "event_tags": self.event_tags,
            "confidence": self.confidence,
            "recency": self.recency,
            "relevance_score": self.relevance_score,
            "conflict_status": self.conflict_status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityEvidence:
        source_raw = data.get("source_type", "tool_result")
        try:
            source_type = EvidenceSourceType(source_raw)
        except ValueError:
            source_type = EvidenceSourceType.TOOL_RESULT
        conflict_raw = data.get("conflict_status", "consistent")
        try:
            conflict_status = ConflictStatus(conflict_raw)
        except ValueError:
            conflict_status = ConflictStatus.CONSISTENT
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            evidence_id=data.get("evidence_id", ""),
            source_type=source_type,
            source_ref=data.get("source_ref", ""),
            source_turn_id=data.get("source_turn_id", ""),
            source_snapshot_id=data.get("source_snapshot_id", ""),
            source_card_state_revision=data.get("source_card_state_revision", 0),
            excerpt=data.get("excerpt", ""),
            entity_refs=data.get("entity_refs", []),
            location_refs=data.get("location_refs", []),
            event_tags=data.get("event_tags", []),
            confidence=data.get("confidence", 0.5),
            recency=data.get("recency", 0.5),
            relevance_score=data.get("relevance_score", 0.5),
            conflict_status=conflict_status,
            created_at=data.get("created_at", ""),
        )

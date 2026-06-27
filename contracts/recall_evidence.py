"""RecallEvidence — a single piece of evidence from history recall.

schemaId: awp.rp.recall-evidence.v1

Each evidence item is traceable to a source (turn, memory, worldbook, etc.)
and carries confidence, recency, and conflict status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.recall-evidence.v1"
SCHEMA_VERSION = 1

# Evidence source priority (highest first)
SOURCE_PRIORITY: dict[str, int] = {
    "card_state": 100,
    "accepted_turn": 90,
    "active_memory": 80,
    "rag_memory": 70,
    "worldbook": 60,
    "tool_result": 50,
}


class EvidenceSourceType:
    """Allowed evidence source types."""
    ACCEPTED_TURN = "accepted_turn"
    ACTIVE_MEMORY = "active_memory"
    RAG_MEMORY = "rag_memory"
    WORLDBOOK = "worldbook"
    CARD_STATE = "card_state"
    TOOL_RESULT = "tool_result"

    ALL = {ACCEPTED_TURN, ACTIVE_MEMORY, RAG_MEMORY, WORLDBOOK, CARD_STATE, TOOL_RESULT}


@dataclass
class RecallEvidence:
    """A single piece of evidence from history recall."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    evidence_id: str = ""
    source_type: str = ""  # One of EvidenceSourceType
    source_ref: str = ""  # Reference to the source (memory_id, turn_id, etc.)
    source_turn_id: str = ""
    source_snapshot_id: str = ""
    source_card_state_revision: int = 0
    excerpt: str = ""  # Short excerpt from the source
    entity_refs: list[str] = field(default_factory=list)
    event_tags: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0-1.0
    recency: float = 0.0  # 0.0-1.0 (1.0 = most recent)
    relevance_score: float = 0.0  # 0.0-1.0
    conflict_status: str = ""  # "" | "stale" | "conflicted" | "ignored"
    conflict_reason: str = ""
    created_at: str = ""

    @property
    def source_priority(self) -> int:
        """Priority based on source type (higher = more authoritative)."""
        return SOURCE_PRIORITY.get(self.source_type, 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "source_turn_id": self.source_turn_id,
            "source_snapshot_id": self.source_snapshot_id,
            "source_card_state_revision": self.source_card_state_revision,
            "excerpt": self.excerpt,
            "entity_refs": list(self.entity_refs),
            "event_tags": list(self.event_tags),
            "confidence": self.confidence,
            "recency": self.recency,
            "relevance_score": self.relevance_score,
            "conflict_status": self.conflict_status,
            "conflict_reason": self.conflict_reason,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecallEvidence:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            evidence_id=data.get("evidence_id", ""),
            source_type=data.get("source_type", ""),
            source_ref=data.get("source_ref", ""),
            source_turn_id=data.get("source_turn_id", ""),
            source_snapshot_id=data.get("source_snapshot_id", ""),
            source_card_state_revision=data.get("source_card_state_revision", 0),
            excerpt=data.get("excerpt", ""),
            entity_refs=list(data.get("entity_refs", [])),
            event_tags=list(data.get("event_tags", [])),
            confidence=data.get("confidence", 0.0),
            recency=data.get("recency", 0.0),
            relevance_score=data.get("relevance_score", 0.0),
            conflict_status=data.get("conflict_status", ""),
            conflict_reason=data.get("conflict_reason", ""),
            created_at=data.get("created_at", ""),
        )

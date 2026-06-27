"""HistoryRecallSuggestion — structured suggestion from History/Recall Agent.

schemaId: awp.rp.history-recall-suggestion.v1

These are NOT final text. They are structured constraints and reminders
for Writer and Director.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.history-recall-suggestion.v1"
SCHEMA_VERSION = 1


class HistorySuggestionKind(str, Enum):
    """Types of history recall suggestions."""
    CONTINUITY_FACT = "continuity_fact"
    RELATIONSHIP_CONTEXT = "relationship_context"
    UNRESOLVED_THREAD = "unresolved_thread"
    HISTORICAL_CONFLICT = "historical_conflict"
    IDENTITY_CLARIFICATION = "identity_clarification"
    TIMELINE_WARNING = "timeline_warning"
    WRITER_CONSTRAINT = "writer_constraint"
    DIRECTOR_FOLLOWUP = "director_followup"


@dataclass
class HistoryRecallSuggestion:
    """A structured suggestion from the History/Recall Agent."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    suggestion_id: str = ""
    kind: HistorySuggestionKind = HistorySuggestionKind.CONTINUITY_FACT
    summary: str = ""  # Short, structured, executable
    details: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    entity_refs: list[str] = field(default_factory=list)
    confidence: float = 0.0
    priority: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "suggestion_id": self.suggestion_id,
            "kind": self.kind.value,
            "summary": self.summary,
            "details": self.details,
            "evidence_refs": list(self.evidence_refs),
            "entity_refs": list(self.entity_refs),
            "confidence": self.confidence,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryRecallSuggestion:
        kind_raw = data.get("kind", "continuity_fact")
        try:
            kind = HistorySuggestionKind(kind_raw)
        except ValueError:
            kind = HistorySuggestionKind.CONTINUITY_FACT
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            suggestion_id=data.get("suggestion_id", ""),
            kind=kind,
            summary=data.get("summary", ""),
            details=data.get("details", ""),
            evidence_refs=list(data.get("evidence_refs", [])),
            entity_refs=list(data.get("entity_refs", [])),
            confidence=data.get("confidence", 0.0),
            priority=data.get("priority", 0.5),
        )

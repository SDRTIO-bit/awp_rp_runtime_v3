"""ContinuitySuggestion — structured suggestion from Continuity Agent.

schemaId: awp.rp.continuity-suggestion.v1

Wraps ContinuityResult into a format consumable by SuggestionMerge.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.continuity-suggestion.v1"
SCHEMA_VERSION = 1


class ContinuitySuggestionKind(str, Enum):
    CONTINUITY_FACT_CONSTRAINT = "continuity_fact_constraint"
    CONTINUITY_BLOCKING_RISK = "continuity_blocking_risk"
    TIMELINE_WARNING = "timeline_warning"
    IDENTITY_WARNING = "identity_warning"
    LOCATION_WARNING = "location_warning"
    KNOWLEDGE_BOUNDARY_WARNING = "knowledge_boundary_warning"
    SUGGESTION_CONFLICT = "suggestion_conflict"
    WRITER_CONSTRAINT = "writer_constraint"
    DIRECTOR_FOLLOWUP = "director_followup"


@dataclass
class ContinuitySuggestion:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    suggestion_id: str = ""
    trace_id: str = ""
    task_run_id: str = ""
    kind: ContinuitySuggestionKind = ContinuitySuggestionKind.WRITER_CONSTRAINT
    priority: float = 0.5
    confidence: float = 0.5
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    writer_constraint: str = ""
    director_recommendation: str = ""
    severity: str = "warning"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "suggestion_id": self.suggestion_id, "trace_id": self.trace_id,
            "task_run_id": self.task_run_id,
            "kind": self.kind.value, "priority": self.priority,
            "confidence": self.confidence, "summary": self.summary,
            "recommendations": self.recommendations,
            "evidence_refs": self.evidence_refs,
            "writer_constraint": self.writer_constraint,
            "director_recommendation": self.director_recommendation,
            "severity": self.severity,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuitySuggestion:
        kind_raw = data.get("kind", "writer_constraint")
        try:
            kind = ContinuitySuggestionKind(kind_raw)
        except ValueError:
            kind = ContinuitySuggestionKind.WRITER_CONSTRAINT
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            suggestion_id=data.get("suggestion_id", ""),
            trace_id=data.get("trace_id", ""),
            task_run_id=data.get("task_run_id", ""),
            kind=kind,
            priority=data.get("priority", 0.5),
            confidence=data.get("confidence", 0.5),
            summary=data.get("summary", ""),
            recommendations=data.get("recommendations", []),
            evidence_refs=data.get("evidence_refs", []),
            writer_constraint=data.get("writer_constraint", ""),
            director_recommendation=data.get("director_recommendation", ""),
            severity=data.get("severity", "warning"),
            created_at=data.get("created_at", ""),
        )

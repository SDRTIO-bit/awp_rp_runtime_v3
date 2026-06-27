"""HistoryRecallResult — structured output of the History/Recall Agent.

schemaId: awp.rp.history-recall-result.v1

Contains evidence, confirmed facts, ambiguous facts, conflicts,
continuity risks, and structured recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .recall_evidence import RecallEvidence
from .continuity_risk import ContinuityRisk
from .history_recall_suggestion import HistoryRecallSuggestion

SCHEMA_ID = "awp.rp.history-recall-result.v1"
SCHEMA_VERSION = 1


class HistoryRecallStatus(str, Enum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"
    NO_TRIGGER = "no_trigger"


@dataclass
class HistoryRecallResult:
    """Structured output of the History/Recall Agent."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    result_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    task_run_id: str = ""

    # Status
    status: HistoryRecallStatus = HistoryRecallStatus.NO_TRIGGER

    # Focus
    focus_entities: list[str] = field(default_factory=list)

    # Evidence (all items must have source_ref)
    evidence: list[RecallEvidence] = field(default_factory=list)

    # Facts (must all bind to evidence)
    confirmed_facts: list[str] = field(default_factory=list)
    ambiguous_facts: list[str] = field(default_factory=list)

    # Conflicts
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    # Unresolved
    unresolved_questions: list[str] = field(default_factory=list)

    # Risks
    continuity_risks: list[ContinuityRisk] = field(default_factory=list)

    # Recommendations (structured, executable — NOT final text)
    writer_recommendations: list[str] = field(default_factory=list)
    director_recommendations: list[str] = field(default_factory=list)

    # Tool usage
    tool_usage: list[dict[str, Any]] = field(default_factory=list)

    # Degradation
    degraded_reasons: list[str] = field(default_factory=list)

    # Suggestions (for SuggestionMerge)
    suggestions: list[HistoryRecallSuggestion] = field(default_factory=list)

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "task_run_id": self.task_run_id,
            "status": self.status.value,
            "focus_entities": list(self.focus_entities),
            "evidence": [e.to_dict() for e in self.evidence],
            "confirmed_facts": list(self.confirmed_facts),
            "ambiguous_facts": list(self.ambiguous_facts),
            "conflicts": list(self.conflicts),
            "unresolved_questions": list(self.unresolved_questions),
            "continuity_risks": [r.to_dict() for r in self.continuity_risks],
            "writer_recommendations": list(self.writer_recommendations),
            "director_recommendations": list(self.director_recommendations),
            "tool_usage": list(self.tool_usage),
            "degraded_reasons": list(self.degraded_reasons),
            "suggestions": [s.to_dict() for s in self.suggestions],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryRecallResult:
        status_raw = data.get("status", "no_trigger")
        try:
            status = HistoryRecallStatus(status_raw)
        except ValueError:
            status = HistoryRecallStatus.NO_TRIGGER
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            result_id=data.get("result_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            task_run_id=data.get("task_run_id", ""),
            status=status,
            focus_entities=list(data.get("focus_entities", [])),
            evidence=[RecallEvidence.from_dict(e) for e in data.get("evidence", [])],
            confirmed_facts=list(data.get("confirmed_facts", [])),
            ambiguous_facts=list(data.get("ambiguous_facts", [])),
            conflicts=list(data.get("conflicts", [])),
            unresolved_questions=list(data.get("unresolved_questions", [])),
            continuity_risks=[ContinuityRisk.from_dict(r) for r in data.get("continuity_risks", [])],
            writer_recommendations=list(data.get("writer_recommendations", [])),
            director_recommendations=list(data.get("director_recommendations", [])),
            tool_usage=list(data.get("tool_usage", [])),
            degraded_reasons=list(data.get("degraded_reasons", [])),
            suggestions=[HistoryRecallSuggestion.from_dict(s) for s in data.get("suggestions", [])],
            created_at=data.get("created_at", ""),
        )

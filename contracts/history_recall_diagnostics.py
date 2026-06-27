"""HistoryRecallDiagnostics — diagnostics for history recall execution.

schemaId: awp.rp.history-recall-diagnostics.v1

Records trigger reasons, tool usage, timing, and degradation info.
Does NOT contain model chain-of-thought or system prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.history-recall-diagnostics.v1"
SCHEMA_VERSION = 1


@dataclass
class HistoryRecallDiagnostics:
    """Diagnostics for a history recall execution."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    diagnostics_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    task_run_id: str = ""

    # Trigger
    trigger_reasons: list[str] = field(default_factory=list)
    suggested_focus_entities: list[str] = field(default_factory=list)
    risk_level: str = "none"

    # Tool usage
    tool_calls_made: int = 0
    tool_calls_succeeded: int = 0
    tool_calls_failed: int = 0
    tool_call_details: list[dict[str, Any]] = field(default_factory=list)

    # Evidence
    evidence_collected: int = 0
    evidence_confirmed: int = 0
    evidence_ambiguous: int = 0
    evidence_conflicted: int = 0

    # Timing
    total_duration_ms: int = 0

    # Degradation
    degraded: bool = False
    degraded_reasons: list[str] = field(default_factory=list)

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "diagnostics_id": self.diagnostics_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "task_run_id": self.task_run_id,
            "trigger_reasons": list(self.trigger_reasons),
            "suggested_focus_entities": list(self.suggested_focus_entities),
            "risk_level": self.risk_level,
            "tool_calls_made": self.tool_calls_made,
            "tool_calls_succeeded": self.tool_calls_succeeded,
            "tool_calls_failed": self.tool_calls_failed,
            "tool_call_details": list(self.tool_call_details),
            "evidence_collected": self.evidence_collected,
            "evidence_confirmed": self.evidence_confirmed,
            "evidence_ambiguous": self.evidence_ambiguous,
            "evidence_conflicted": self.evidence_conflicted,
            "total_duration_ms": self.total_duration_ms,
            "degraded": self.degraded,
            "degraded_reasons": list(self.degraded_reasons),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryRecallDiagnostics:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            diagnostics_id=data.get("diagnostics_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            task_run_id=data.get("task_run_id", ""),
            trigger_reasons=list(data.get("trigger_reasons", [])),
            suggested_focus_entities=list(data.get("suggested_focus_entities", [])),
            risk_level=data.get("risk_level", "none"),
            tool_calls_made=data.get("tool_calls_made", 0),
            tool_calls_succeeded=data.get("tool_calls_succeeded", 0),
            tool_calls_failed=data.get("tool_calls_failed", 0),
            tool_call_details=list(data.get("tool_call_details", [])),
            evidence_collected=data.get("evidence_collected", 0),
            evidence_confirmed=data.get("evidence_confirmed", 0),
            evidence_ambiguous=data.get("evidence_ambiguous", 0),
            evidence_conflicted=data.get("evidence_conflicted", 0),
            total_duration_ms=data.get("total_duration_ms", 0),
            degraded=data.get("degraded", False),
            degraded_reasons=list(data.get("degraded_reasons", [])),
            created_at=data.get("created_at", ""),
        )

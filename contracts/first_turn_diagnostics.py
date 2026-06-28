"""First Turn Diagnostics -- trace and diagnostic info for first turn execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.first-turn-diagnostics.v1"
SCHEMA_VERSION = 1


@dataclass
class FirstTurnDiagnostics:
    """Diagnostic information produced during first turn execution.

    Contains step-level timing, validation results, worldbook retrieval
    explanation, dynamic agent dispositions, quality gate details,
    commit status, and memory curation outcome.
    """

    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    diagnostics_id: str = ""
    request_id: str = ""
    trace_id: str = ""
    session_id: str = ""
    # Step tracking
    steps_completed: list[str] = field(default_factory=list)
    steps_failed: list[str] = field(default_factory=list)
    step_timings_ms: dict[str, int] = field(default_factory=dict)
    # Validation
    validation_errors: list[str] = field(default_factory=list)
    # Session info
    session_status: str = ""
    binding_card_version: int = 0
    binding_source_hash: str = ""
    # Worldbook retrieval explanation
    worldbook_candidate_count: int = 0
    worldbook_activated_count: int = 0
    worldbook_rejected_count: int = 0
    worldbook_deferred_count: int = 0
    worldbook_disabled_count: int = 0
    worldbook_budget_dropped_count: int = 0
    # Dynamic agent dispositions
    agent_dispositions: dict[str, str] = field(default_factory=dict)
    # Quality gate
    quality_verdict: str = ""
    quality_blocking_reasons: list[str] = field(default_factory=list)
    # Commit status
    card_state_commit_status: str = ""
    turn_record_commit_status: str = ""
    # Memory curation
    memory_curation_status: str = ""
    memory_curation_reason: str = ""
    # Outcome
    outcome: str = ""  # success | failure | quality_rejected
    failure_code: str = ""
    failure_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "diagnostics_id": self.diagnostics_id,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "steps_completed": list(self.steps_completed),
            "steps_failed": list(self.steps_failed),
            "step_timings_ms": dict(self.step_timings_ms),
            "validation_errors": list(self.validation_errors),
            "session_status": self.session_status,
            "binding_card_version": self.binding_card_version,
            "binding_source_hash": self.binding_source_hash,
            "worldbook_candidate_count": self.worldbook_candidate_count,
            "worldbook_activated_count": self.worldbook_activated_count,
            "worldbook_rejected_count": self.worldbook_rejected_count,
            "worldbook_deferred_count": self.worldbook_deferred_count,
            "worldbook_disabled_count": self.worldbook_disabled_count,
            "worldbook_budget_dropped_count": self.worldbook_budget_dropped_count,
            "agent_dispositions": dict(self.agent_dispositions),
            "quality_verdict": self.quality_verdict,
            "quality_blocking_reasons": list(self.quality_blocking_reasons),
            "card_state_commit_status": self.card_state_commit_status,
            "turn_record_commit_status": self.turn_record_commit_status,
            "memory_curation_status": self.memory_curation_status,
            "memory_curation_reason": self.memory_curation_reason,
            "outcome": self.outcome,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FirstTurnDiagnostics:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            diagnostics_id=data.get("diagnostics_id", ""),
            request_id=data.get("request_id", ""),
            trace_id=data.get("trace_id", ""),
            session_id=data.get("session_id", ""),
            steps_completed=list(data.get("steps_completed", [])),
            steps_failed=list(data.get("steps_failed", [])),
            step_timings_ms=dict(data.get("step_timings_ms", {})),
            validation_errors=list(data.get("validation_errors", [])),
            session_status=data.get("session_status", ""),
            binding_card_version=data.get("binding_card_version", 0),
            binding_source_hash=data.get("binding_source_hash", ""),
            worldbook_candidate_count=data.get("worldbook_candidate_count", 0),
            worldbook_activated_count=data.get("worldbook_activated_count", 0),
            worldbook_rejected_count=data.get("worldbook_rejected_count", 0),
            worldbook_deferred_count=data.get("worldbook_deferred_count", 0),
            worldbook_disabled_count=data.get("worldbook_disabled_count", 0),
            worldbook_budget_dropped_count=data.get("worldbook_budget_dropped_count", 0),
            agent_dispositions=dict(data.get("agent_dispositions", {})),
            quality_verdict=data.get("quality_verdict", ""),
            quality_blocking_reasons=list(data.get("quality_blocking_reasons", [])),
            card_state_commit_status=data.get("card_state_commit_status", ""),
            turn_record_commit_status=data.get("turn_record_commit_status", ""),
            memory_curation_status=data.get("memory_curation_status", ""),
            memory_curation_reason=data.get("memory_curation_reason", ""),
            outcome=data.get("outcome", ""),
            failure_code=data.get("failure_code", ""),
            failure_message=data.get("failure_message", ""),
        )

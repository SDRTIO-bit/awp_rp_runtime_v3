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
    # Provider / profile evidence (LSS-V1)
    director_profile_id: str = ""
    writer_profile_id: str = ""
    director_provider_type: str = ""  # "fake" | "deepseek"
    writer_provider_type: str = ""
    director_model: str = ""
    writer_model: str = ""
    director_call_success: bool = False
    writer_call_success: bool = False
    director_failure_code: str = ""
    writer_failure_code: str = ""
    # Memory-use evidence (LSS-V1) — IDs only, never raw content/keys
    l1_turn_ids_recalled: list[str] = field(default_factory=list)
    l2_memory_ids_recalled: list[str] = field(default_factory=list)
    l3_memory_ids_recalled: list[str] = field(default_factory=list)
    worldbook_entry_ids_considered: list[str] = field(default_factory=list)
    worldbook_entry_ids_activated: list[str] = field(default_factory=list)
    round_snapshot_id: str = ""
    director_plan_ref: str = ""  # plan_id or hash
    card_state_revision_before: int = 0
    card_state_revision_after: int = 0
    turn_record_id: str = ""
    memory_commit_ids: list[str] = field(default_factory=list)
    active_memory_committed_ids: list[str] = field(default_factory=list)
    rag_memory_committed_ids: list[str] = field(default_factory=list)
    trace_persisted: bool = False
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
            "director_profile_id": self.director_profile_id,
            "writer_profile_id": self.writer_profile_id,
            "director_provider_type": self.director_provider_type,
            "writer_provider_type": self.writer_provider_type,
            "director_model": self.director_model,
            "writer_model": self.writer_model,
            "director_call_success": self.director_call_success,
            "writer_call_success": self.writer_call_success,
            "director_failure_code": self.director_failure_code,
            "writer_failure_code": self.writer_failure_code,
            "l1_turn_ids_recalled": list(self.l1_turn_ids_recalled),
            "l2_memory_ids_recalled": list(self.l2_memory_ids_recalled),
            "l3_memory_ids_recalled": list(self.l3_memory_ids_recalled),
            "worldbook_entry_ids_considered": list(self.worldbook_entry_ids_considered),
            "worldbook_entry_ids_activated": list(self.worldbook_entry_ids_activated),
            "round_snapshot_id": self.round_snapshot_id,
            "director_plan_ref": self.director_plan_ref,
            "card_state_revision_before": self.card_state_revision_before,
            "card_state_revision_after": self.card_state_revision_after,
            "turn_record_id": self.turn_record_id,
            "memory_commit_ids": list(self.memory_commit_ids),
            "active_memory_committed_ids": list(self.active_memory_committed_ids),
            "rag_memory_committed_ids": list(self.rag_memory_committed_ids),
            "trace_persisted": self.trace_persisted,
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
            director_profile_id=data.get("director_profile_id", ""),
            writer_profile_id=data.get("writer_profile_id", ""),
            director_provider_type=data.get("director_provider_type", ""),
            writer_provider_type=data.get("writer_provider_type", ""),
            director_model=data.get("director_model", ""),
            writer_model=data.get("writer_model", ""),
            director_call_success=data.get("director_call_success", False),
            writer_call_success=data.get("writer_call_success", False),
            director_failure_code=data.get("director_failure_code", ""),
            writer_failure_code=data.get("writer_failure_code", ""),
            l1_turn_ids_recalled=list(data.get("l1_turn_ids_recalled", [])),
            l2_memory_ids_recalled=list(data.get("l2_memory_ids_recalled", [])),
            l3_memory_ids_recalled=list(data.get("l3_memory_ids_recalled", [])),
            worldbook_entry_ids_considered=list(data.get("worldbook_entry_ids_considered", [])),
            worldbook_entry_ids_activated=list(data.get("worldbook_entry_ids_activated", [])),
            round_snapshot_id=data.get("round_snapshot_id", ""),
            director_plan_ref=data.get("director_plan_ref", ""),
            card_state_revision_before=data.get("card_state_revision_before", 0),
            card_state_revision_after=data.get("card_state_revision_after", 0),
            turn_record_id=data.get("turn_record_id", ""),
            memory_commit_ids=list(data.get("memory_commit_ids", [])),
            active_memory_committed_ids=list(data.get("active_memory_committed_ids", [])),
            rag_memory_committed_ids=list(data.get("rag_memory_committed_ids", [])),
            trace_persisted=data.get("trace_persisted", False),
            outcome=data.get("outcome", ""),
            failure_code=data.get("failure_code", ""),
            failure_message=data.get("failure_message", ""),
        )

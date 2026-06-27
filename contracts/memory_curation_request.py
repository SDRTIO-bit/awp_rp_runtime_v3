"""MemoryCurationRequest — formal input for the Memory Curator Agent.

schemaId: awp.rp.memory-curation-request.v1

Contains all the data the Memory Curator needs to read (never write).
Must bind to accepted facts only — no drafts, no rejects, no raw CoT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.memory-curation-request.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MemoryCurationRequest:
    """Formal request to the Memory Curator Agent.

    All inputs are read-only references. The Curator cannot write stores,
    cannot modify CardState, cannot generate final text, cannot delegate.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity & isolation
    request_id: str = ""
    trace_id: str = ""
    task_run_id: str = ""
    card_id: str = ""
    session_id: str = ""
    turn_id: str = ""

    # Accepted facts only (never draft / reject / raw CoT)
    accepted_turn_record_ref: str = ""      # turn_id of the accepted TurnRecord
    accepted_output: str = ""               # the accepted writer output text
    player_input: str = ""                  # the player input for this turn
    quality_decision_ref: str = ""          # trace_id of the accepting QualityDecision
    card_state_commit_ref: str = ""         # patch_id of the CardStateCommit
    turn_record_commit_ref: str = ""        # turn_id of the TurnRecordCommit
    card_state_delta_summary: str = ""      # summary of what changed in CardState

    # Current memory snapshots (read-only)
    active_memory_snapshot: list[dict[str, Any]] = field(default_factory=list)
    rag_memory_snapshot: list[dict[str, Any]] = field(default_factory=list)

    # Accepted turn window (L1, read-only)
    recent_turn_records: list[dict[str, Any]] = field(default_factory=list)

    # CardState snapshot (read-only)
    card_state_snapshot: dict[str, Any] = field(default_factory=dict)

    # Constraints
    max_active_candidates: int = 5
    max_rag_candidates: int = 5
    idempotency_key: str = ""

    # Hard prohibitions (always True)
    must_use_accepted_facts_only: bool = True
    must_not_create_facts: bool = True
    must_not_write_storage: bool = True

    # Budget
    max_tool_calls: int = 0
    timeout_ms: int = 30000

    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "task_run_id": self.task_run_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "accepted_turn_record_ref": self.accepted_turn_record_ref,
            "accepted_output": self.accepted_output,
            "player_input": self.player_input,
            "quality_decision_ref": self.quality_decision_ref,
            "card_state_commit_ref": self.card_state_commit_ref,
            "turn_record_commit_ref": self.turn_record_commit_ref,
            "card_state_delta_summary": self.card_state_delta_summary,
            "active_memory_snapshot": list(self.active_memory_snapshot),
            "rag_memory_snapshot": list(self.rag_memory_snapshot),
            "recent_turn_records": list(self.recent_turn_records),
            "card_state_snapshot": dict(self.card_state_snapshot),
            "max_active_candidates": self.max_active_candidates,
            "max_rag_candidates": self.max_rag_candidates,
            "idempotency_key": self.idempotency_key,
            "must_use_accepted_facts_only": self.must_use_accepted_facts_only,
            "must_not_create_facts": self.must_not_create_facts,
            "must_not_write_storage": self.must_not_write_storage,
            "max_tool_calls": self.max_tool_calls,
            "timeout_ms": self.timeout_ms,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCurationRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            trace_id=data.get("trace_id", ""),
            task_run_id=data.get("task_run_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            turn_id=data.get("turn_id", ""),
            accepted_turn_record_ref=data.get("accepted_turn_record_ref", ""),
            accepted_output=data.get("accepted_output", ""),
            player_input=data.get("player_input", ""),
            quality_decision_ref=data.get("quality_decision_ref", ""),
            card_state_commit_ref=data.get("card_state_commit_ref", ""),
            turn_record_commit_ref=data.get("turn_record_commit_ref", ""),
            card_state_delta_summary=data.get("card_state_delta_summary", ""),
            active_memory_snapshot=list(data.get("active_memory_snapshot", [])),
            rag_memory_snapshot=list(data.get("rag_memory_snapshot", [])),
            recent_turn_records=list(data.get("recent_turn_records", [])),
            card_state_snapshot=dict(data.get("card_state_snapshot", {})),
            max_active_candidates=data.get("max_active_candidates", 5),
            max_rag_candidates=data.get("max_rag_candidates", 5),
            idempotency_key=data.get("idempotency_key", ""),
            must_use_accepted_facts_only=data.get("must_use_accepted_facts_only", True),
            must_not_create_facts=data.get("must_not_create_facts", True),
            must_not_write_storage=data.get("must_not_write_storage", True),
            max_tool_calls=data.get("max_tool_calls", 0),
            timeout_ms=data.get("timeout_ms", 30000),
            created_at=data.get("created_at", ""),
        )

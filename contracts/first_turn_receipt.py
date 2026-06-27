"""First Turn Receipt and Failure contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RECEIPT_SCHEMA_ID = "awp.rp.first-turn-receipt.v1"
RECEIPT_SCHEMA_VERSION = 1

FAILURE_SCHEMA_ID = "awp.rp.first-turn-failure.v1"
FAILURE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FirstTurnReceipt:
    """Successful completion receipt for a first formal RP turn.

    Issued only when Quality Gate accepts, CardState commits,
    TurnRecord commits, and D6 completes (or is explicitly no-op).
    """

    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: int = RECEIPT_SCHEMA_VERSION
    receipt_id: str = ""
    request_id: str = ""
    workflow_run_id: str = ""
    trace_id: str = ""
    turn_id: str = ""
    attempt_id: str = ""
    session_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    source_hash: str = ""
    # Turn outcome
    accepted_text: str = ""
    quality_verdict: str = ""
    # State changes
    base_card_state_revision: int = 0
    result_card_state_revision: int = 0
    card_state_commit_status: str = ""
    # Turn record
    turn_record_id: str = ""
    turn_index: int = 0
    turn_record_commit_status: str = ""
    # Memory curation
    memory_curation_status: str = "noop"
    active_memory_write_count: int = 0
    rag_memory_write_count: int = 0
    # Idempotency
    idempotency_status: str = ""
    # Timing
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "request_id": self.request_id,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "source_hash": self.source_hash,
            "accepted_text": self.accepted_text,
            "quality_verdict": self.quality_verdict,
            "base_card_state_revision": self.base_card_state_revision,
            "result_card_state_revision": self.result_card_state_revision,
            "card_state_commit_status": self.card_state_commit_status,
            "turn_record_id": self.turn_record_id,
            "turn_index": self.turn_index,
            "turn_record_commit_status": self.turn_record_commit_status,
            "memory_curation_status": self.memory_curation_status,
            "active_memory_write_count": self.active_memory_write_count,
            "rag_memory_write_count": self.rag_memory_write_count,
            "idempotency_status": self.idempotency_status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FirstTurnReceipt:
        return cls(
            schema_id=data.get("schema_id", RECEIPT_SCHEMA_ID),
            schema_version=data.get("schema_version", RECEIPT_SCHEMA_VERSION),
            receipt_id=data.get("receipt_id", ""),
            request_id=data.get("request_id", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            attempt_id=data.get("attempt_id", ""),
            session_id=data.get("session_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            source_hash=data.get("source_hash", ""),
            accepted_text=data.get("accepted_text", ""),
            quality_verdict=data.get("quality_verdict", ""),
            base_card_state_revision=data.get("base_card_state_revision", 0),
            result_card_state_revision=data.get("result_card_state_revision", 0),
            card_state_commit_status=data.get("card_state_commit_status", ""),
            turn_record_id=data.get("turn_record_id", ""),
            turn_index=data.get("turn_index", 0),
            turn_record_commit_status=data.get("turn_record_commit_status", ""),
            memory_curation_status=data.get("memory_curation_status", "noop"),
            active_memory_write_count=data.get("active_memory_write_count", 0),
            rag_memory_write_count=data.get("rag_memory_write_count", 0),
            idempotency_status=data.get("idempotency_status", ""),
            created_at=data.get("created_at", ""),
        )


class FirstTurnFailureCode:
    """Structured failure codes for first turn execution."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_NOT_READY = "SESSION_NOT_READY"
    BINDING_NOT_FOUND = "BINDING_NOT_FOUND"
    CARD_VERSION_MISMATCH = "CARD_VERSION_MISMATCH"
    SOURCE_HASH_MISMATCH = "SOURCE_HASH_MISMATCH"
    OPENING_RECORD_NOT_FOUND = "OPENING_RECORD_NOT_FOUND"
    WORLDBOOK_BINDING_NOT_FOUND = "WORLDBOOK_BINDING_NOT_FOUND"
    QUALITY_REJECTED = "QUALITY_REJECTED"
    STATE_COMMIT_FAILED = "STATE_COMMIT_FAILED"
    TURN_COMMIT_FAILED = "TURN_COMMIT_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class FirstTurnFailure:
    """Structured failure for first turn execution.

    Issued when any validation or execution step fails.
    No Director, Writer, or Memory operations have been triggered.
    """

    schema_id: str = FAILURE_SCHEMA_ID
    schema_version: int = FAILURE_SCHEMA_VERSION
    failure_id: str = ""
    request_id: str = ""
    workflow_run_id: str = ""
    trace_id: str = ""
    turn_id: str = ""
    attempt_id: str = ""
    session_id: str = ""
    failure_code: str = ""
    failure_message: str = ""
    failed_at_step: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "failure_id": self.failure_id,
            "request_id": self.request_id,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "failed_at_step": self.failed_at_step,
            "diagnostics": dict(self.diagnostics),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FirstTurnFailure:
        return cls(
            schema_id=data.get("schema_id", FAILURE_SCHEMA_ID),
            schema_version=data.get("schema_version", FAILURE_SCHEMA_VERSION),
            failure_id=data.get("failure_id", ""),
            request_id=data.get("request_id", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            attempt_id=data.get("attempt_id", ""),
            session_id=data.get("session_id", ""),
            failure_code=data.get("failure_code", ""),
            failure_message=data.get("failure_message", ""),
            failed_at_step=data.get("failed_at_step", ""),
            diagnostics=dict(data.get("diagnostics", {})),
            created_at=data.get("created_at", ""),
        )

"""MemoryCommitPlan / Request / Receipt / Result — formal memory commit contracts.

schemaId: awp.rp.memory-commit-plan.v1

Memory may only be written after a turn is accepted. Formal order:
  Writer → QualityGate accept → StateUpdateProposal → SideEffectDecision
  → CardStateCommit success → TurnRecordCommit success
  → ActiveMemoryCommit → RAGMemoryCommit

The plan is a *proposal*. Only the commit runtimes may write, and only after
full gate validation + idempotency check. retry uses a new memoryCommitId;
the same idempotencyKey replayed returns the original receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .active_memory import ActiveMemoryRecord, ActiveMemoryEntry
from .rag_memory import RagMemoryRecord, RagMemoryEntry

SCHEMA_ID = "awp.rp.memory-commit-plan.v1"
SCHEMA_VERSION = 1

REQUEST_SCHEMA_ID = "awp.rp.memory-commit-request.v1"
RECEIPT_SCHEMA_ID = "awp.rp.memory-commit-receipt.v1"
RESULT_SCHEMA_ID = "awp.rp.memory-commit-result.v1"


@dataclass
class MemoryCommitPlan:
    """Plan for committing to memory stores.

    Validated before writes. Only commit runtimes can write.
    Carries traceability fields so the commit runtime can verify gate + state
    + turn commits and enforce idempotency.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    turn_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Traceability / idempotency
    trace_id: str = ""
    expected_card_state_revision: int = 0
    memory_commit_id: str = ""
    idempotency_key: str = ""
    quality_decision_ref: str = ""  # trace_id of the accepting QualityDecision

    # Active memory changes
    new_active_entries: list[ActiveMemoryRecord] = field(default_factory=list)
    updated_active_entries: list[ActiveMemoryRecord] = field(default_factory=list)
    resolved_active_ids: list[str] = field(default_factory=list)

    # RAG memory changes
    new_rag_entries: list[RagMemoryRecord] = field(default_factory=list)

    # Provenance: why each memory is written
    write_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "turn_id": self.turn_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "expected_card_state_revision": self.expected_card_state_revision,
            "memory_commit_id": self.memory_commit_id,
            "idempotency_key": self.idempotency_key,
            "quality_decision_ref": self.quality_decision_ref,
            "new_active_entries": [e.to_dict() for e in self.new_active_entries],
            "updated_active_entries": [e.to_dict() for e in self.updated_active_entries],
            "resolved_active_ids": list(self.resolved_active_ids),
            "new_rag_entries": [e.to_dict() for e in self.new_rag_entries],
            "write_reasons": list(self.write_reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCommitPlan:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            turn_id=data.get("turn_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            trace_id=data.get("trace_id", ""),
            expected_card_state_revision=data.get("expected_card_state_revision", 0),
            memory_commit_id=data.get("memory_commit_id", ""),
            idempotency_key=data.get("idempotency_key", ""),
            quality_decision_ref=data.get("quality_decision_ref", ""),
            new_active_entries=[ActiveMemoryRecord.from_dict(e) for e in data.get("new_active_entries", [])],
            updated_active_entries=[ActiveMemoryRecord.from_dict(e) for e in data.get("updated_active_entries", [])],
            resolved_active_ids=list(data.get("resolved_active_ids", [])),
            new_rag_entries=[RagMemoryRecord.from_dict(e) for e in data.get("new_rag_entries", [])],
            write_reasons=list(data.get("write_reasons", [])),
        )


@dataclass(frozen=True)
class MemoryCommitRequest:
    """Formal request to commit memory for an accepted turn.

    Bundles everything the commit runtime needs to enforce the gate:
      - plan: the proposed memory changes
      - quality_decision_ref / trace_id: gate provenance
      - card_state_commit_success / turn_record_commit_success: upstream commits
      - expected_card_state_revision: must match the committed CardState
      - memory_commit_id / idempotency_key: idempotency
    """
    schema_id: str = REQUEST_SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    plan: MemoryCommitPlan = field(default_factory=MemoryCommitPlan)

    card_id: str = ""
    session_id: str = ""
    turn_id: str = ""
    trace_id: str = ""
    memory_commit_id: str = ""
    idempotency_key: str = ""
    quality_decision_ref: str = ""
    expected_card_state_revision: int = 0

    # Upstream commit outcomes (deterministic gate inputs)
    card_state_commit_success: bool = False
    turn_record_commit_success: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "plan": self.plan.to_dict(),
            "card_id": self.card_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "trace_id": self.trace_id,
            "memory_commit_id": self.memory_commit_id,
            "idempotency_key": self.idempotency_key,
            "quality_decision_ref": self.quality_decision_ref,
            "expected_card_state_revision": self.expected_card_state_revision,
            "card_state_commit_success": self.card_state_commit_success,
            "turn_record_commit_success": self.turn_record_commit_success,
        }


@dataclass(frozen=True)
class MemoryCommitReceipt:
    """Idempotent receipt for one memory commit. Replaying the same
    idempotency_key returns the original receipt."""
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    memory_commit_id: str = ""
    idempotency_key: str = ""
    turn_id: str = ""
    card_id: str = ""
    session_id: str = ""
    trace_id: str = ""
    expected_card_state_revision: int = 0
    quality_decision_ref: str = ""

    committed_active_ids: list[str] = field(default_factory=list)
    committed_rag_ids: list[str] = field(default_factory=list)
    evicted_active_ids: list[str] = field(default_factory=list)

    committed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "memory_commit_id": self.memory_commit_id,
            "idempotency_key": self.idempotency_key,
            "turn_id": self.turn_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "expected_card_state_revision": self.expected_card_state_revision,
            "quality_decision_ref": self.quality_decision_ref,
            "committed_active_ids": list(self.committed_active_ids),
            "committed_rag_ids": list(self.committed_rag_ids),
            "evicted_active_ids": list(self.evicted_active_ids),
            "committed_at": self.committed_at,
        }


class MemoryCommitStatus:
    """Outcome status of a memory commit attempt."""
    COMMITTED = "committed"
    BLOCKED_NO_GATE = "blocked_no_gate"
    BLOCKED_GATE_NOT_ACCEPT = "blocked_gate_not_accept"
    BLOCKED_TRACE_MISMATCH = "blocked_trace_mismatch"
    BLOCKED_CARD_STATE = "blocked_card_state_commit"
    BLOCKED_TURN_RECORD = "blocked_turn_record_commit"
    BLOCKED_REVISION_MISMATCH = "blocked_revision_mismatch"
    BLOCKED_VALIDATION = "blocked_validation"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class MemoryCommitResult:
    """Result of a memory commit attempt (zero side effects on any block)."""
    schema_id: str = RESULT_SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    status: str = MemoryCommitStatus.SKIPPED
    receipt: MemoryCommitReceipt | None = None
    error_message: str = ""
    layer: str = ""  # "active" | "rag"

    @property
    def success(self) -> bool:
        return self.status in (MemoryCommitStatus.COMMITTED, MemoryCommitStatus.IDEMPOTENT_REPLAY)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "status": self.status,
            "receipt": self.receipt.to_dict() if self.receipt else None,
            "error_message": self.error_message,
            "layer": self.layer,
        }


__all__ = [
    "SCHEMA_ID", "SCHEMA_VERSION",
    "MemoryCommitPlan",
    "MemoryCommitRequest", "MemoryCommitReceipt", "MemoryCommitResult",
    "MemoryCommitStatus",
    "ActiveMemoryRecord", "ActiveMemoryEntry",
    "RagMemoryRecord", "RagMemoryEntry",
]

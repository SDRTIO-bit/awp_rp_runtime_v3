"""RagMemoryCommitRuntime — commits to L3 long-term RAG memory.

Gate must pass before any writes. Same formal order as active memory.
Idempotent via idempotency_key. Defaults to `session` scope; `card_global`
must be declared explicitly on the record. No cross-cardId sharing.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..contracts.memory_commit_plan import (
    MemoryCommitPlan, MemoryCommitRequest, MemoryCommitReceipt,
    MemoryCommitResult, MemoryCommitStatus, RagMemoryEntry,
)
from ..contracts.quality_decision import QualityDecision
from ..contracts.rag_memory import RagMemoryScope
from .novel_memory_policy import MemoryPolicy
from ..storage.interfaces import RagMemoryStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RagMemoryCommitRuntime:

    def __init__(self, store: RagMemoryStore, policy: MemoryPolicy | None = None):
        self.store = store
        self.policy = policy or MemoryPolicy()

    # ---- Formal entry: full gate + idempotency ----
    def commit_request(
        self,
        request: MemoryCommitRequest,
        quality_decision: QualityDecision | None,
    ) -> MemoryCommitResult:
        """Commit RAG memory with full gate validation. Zero side effects on any block."""
        if quality_decision is None:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_NO_GATE, layer="rag",
                error_message="No QualityDecision provided",
            )
        if not quality_decision.is_accepted():
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_GATE_NOT_ACCEPT, layer="rag",
                error_message=f"Gate not accept: {quality_decision.verdict.value}",
            )
        if quality_decision.trace_id and request.trace_id and \
                request.trace_id != quality_decision.trace_id:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_TRACE_MISMATCH, layer="rag",
                error_message=(
                    f"trace mismatch: request={request.trace_id} "
                    f"gate={quality_decision.trace_id}"
                ),
            )
        if not request.card_state_commit_success:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_CARD_STATE, layer="rag",
                error_message="CardStateCommit did not succeed",
            )
        if not request.turn_record_commit_success:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_TURN_RECORD, layer="rag",
                error_message="TurnRecordCommit did not succeed",
            )
        # Validate plan + scope safety
        validation = self.policy.validate_commit_plan(request.plan, current_active_count=0)
        if not validation.valid:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_VALIDATION, layer="rag",
                error_message=f"Invalid plan: {validation.errors}",
            )
        # Enforce scope safety: card_global must not cross cardId
        for entry in request.plan.new_rag_entries:
            if entry.scope == RagMemoryScope.CARD_GLOBAL.value and \
                    entry.card_id and entry.card_id != request.card_id:
                return MemoryCommitResult(
                    status=MemoryCommitStatus.BLOCKED_VALIDATION, layer="rag",
                    error_message=f"card_global scope crosses cardId: {entry.memory_id}",
                )

        # Idempotency
        existing = self.store.get_receipt_by_idempotency_key(
            request.card_id, request.session_id, request.idempotency_key
        )
        if existing is not None:
            return MemoryCommitResult(
                status=MemoryCommitStatus.IDEMPOTENT_REPLAY, layer="rag",
                receipt=existing,
                error_message="Idempotent replay — no writes",
            )

        committed_ids: list[str] = []
        for entry in request.plan.new_rag_entries:
            # Default scope = session; never auto-leak to card_global
            if not entry.scope:
                entry = RagMemoryEntry(**{**entry.to_dict(), "scope": RagMemoryScope.SESSION.value})
            # Force isolation: stamp card_id+session_id onto the record
            entry = RagMemoryEntry(**{
                **entry.to_dict(),
                "card_id": request.card_id,
                "session_id": request.session_id,
            })
            self.store.save(request.card_id, request.session_id, entry)
            committed_ids.append(entry.memory_id)

        receipt = MemoryCommitReceipt(
            memory_commit_id=request.memory_commit_id,
            idempotency_key=request.idempotency_key,
            turn_id=request.turn_id,
            card_id=request.card_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            expected_card_state_revision=request.expected_card_state_revision,
            quality_decision_ref=request.quality_decision_ref,
            committed_rag_ids=committed_ids,
            committed_at=_now(),
        )
        self.store.record_receipt(receipt)

        return MemoryCommitResult(
            status=MemoryCommitStatus.COMMITTED, layer="rag", receipt=receipt,
        )

    # ---- Legacy entry ----
    def commit(
        self,
        plan: MemoryCommitPlan,
        card_id: str,
        session_id: str,
        quality_decision: QualityDecision,
    ) -> list[RagMemoryEntry]:
        """Legacy commit. Gate must accept."""
        from ..contracts.quality_decision import assert_side_effects_allowed
        assert_side_effects_allowed(quality_decision)

        saved = []
        for entry in plan.new_rag_entries:
            if not entry.scope:
                entry = RagMemoryEntry(**{**entry.to_dict(), "scope": RagMemoryScope.SESSION.value})
            self.store.save(card_id, session_id, entry)
            saved.append(entry)
        return saved

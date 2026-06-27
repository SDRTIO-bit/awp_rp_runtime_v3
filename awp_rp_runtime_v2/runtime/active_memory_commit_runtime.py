"""ActiveMemoryCommitRuntime — commits to L2 active memory.

Gate must pass before any writes. Formal order enforced:
  QualityGate accept → CardStateCommit success → TurnRecordCommit success
  → ActiveMemoryCommit.

Idempotent: replaying the same idempotency_key returns the original receipt
with zero side effects. retry uses a new memory_commit_id. When the 15-slot is
full, a deterministic retention policy evicts the lowest-priority records
(no random, no LLM silent overwrite).
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..contracts.memory_commit_plan import (
    MemoryCommitPlan, MemoryCommitRequest, MemoryCommitReceipt,
    MemoryCommitResult, MemoryCommitStatus, ActiveMemoryEntry,
)
from ..contracts.quality_decision import QualityDecision
from ..contracts.active_memory import ActiveMemoryStatus
from ..contracts.memory_retention_decision import MemoryRetentionResult
from ..policies.memory_policy import MemoryPolicy
from ..storage.interfaces import ActiveMemoryStore, RetentionDecisionStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActiveMemoryCommitRuntime:

    def __init__(
        self,
        store: ActiveMemoryStore,
        policy: MemoryPolicy | None = None,
        retention_store: RetentionDecisionStore | None = None,
    ):
        self.store = store
        self.policy = policy or MemoryPolicy()
        self.retention_store = retention_store

    # ---- Formal entry: full gate + idempotency + retention ----
    def commit_request(
        self,
        request: MemoryCommitRequest,
        quality_decision: QualityDecision | None,
    ) -> MemoryCommitResult:
        """Commit active memory with full gate validation. Zero side effects on any block."""
        # 1. Gate exists
        if quality_decision is None:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_NO_GATE, layer="active",
                error_message="No QualityDecision provided",
            )
        # 2. Gate accepted
        if not quality_decision.is_accepted():
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_GATE_NOT_ACCEPT, layer="active",
                error_message=f"Gate not accept: {quality_decision.verdict.value}",
            )
        # 3. traceId match
        if quality_decision.trace_id and request.trace_id and \
                request.trace_id != quality_decision.trace_id:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_TRACE_MISMATCH, layer="active",
                error_message=(
                    f"trace mismatch: request={request.trace_id} "
                    f"gate={quality_decision.trace_id}"
                ),
            )
        # 4. CardStateCommit success
        if not request.card_state_commit_success:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_CARD_STATE, layer="active",
                error_message="CardStateCommit did not succeed",
            )
        # 5. TurnRecordCommit success
        if not request.turn_record_commit_success:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_TURN_RECORD, layer="active",
                error_message="TurnRecordCommit did not succeed",
            )
        # 6. Validate plan
        current_count = self.store.get_active_count(request.card_id, request.session_id)
        validation = self.policy.validate_commit_plan(request.plan, current_count)
        if not validation.valid:
            return MemoryCommitResult(
                status=MemoryCommitStatus.BLOCKED_VALIDATION, layer="active",
                error_message=f"Invalid plan: {validation.errors}",
            )
        # 7. Idempotency: replay returns original receipt
        existing = self.store.get_receipt_by_idempotency_key(
            request.card_id, request.session_id, request.idempotency_key
        )
        if existing is not None:
            return MemoryCommitResult(
                status=MemoryCommitStatus.IDEMPOTENT_REPLAY, layer="active",
                receipt=existing,
                error_message="Idempotent replay — no writes",
            )

        # 8. Apply writes
        plan = request.plan
        for mid in plan.resolved_active_ids:
            self.store.resolve(request.card_id, request.session_id, mid)
        for entry in plan.new_active_entries:
            self.store.upsert(request.card_id, request.session_id, entry)
        for entry in plan.updated_active_entries:
            self.store.upsert(request.card_id, request.session_id, entry)

        # 9. Deterministic retention (15-slot)
        evicted_ids = self._enforce_retention(request, plan)

        committed_ids = [e.memory_id for e in plan.new_active_entries] + \
            [e.memory_id for e in plan.updated_active_entries]

        receipt = MemoryCommitReceipt(
            memory_commit_id=request.memory_commit_id,
            idempotency_key=request.idempotency_key,
            turn_id=request.turn_id,
            card_id=request.card_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            expected_card_state_revision=request.expected_card_state_revision,
            quality_decision_ref=request.quality_decision_ref,
            committed_active_ids=committed_ids,
            evicted_active_ids=evicted_ids,
            committed_at=_now(),
        )
        self.store.record_receipt(receipt)

        return MemoryCommitResult(
            status=MemoryCommitStatus.COMMITTED, layer="active", receipt=receipt,
        )

    def _enforce_retention(
        self, request: MemoryCommitRequest, plan: MemoryCommitPlan
    ) -> list[str]:
        """If active count exceeds 15, deterministically evict lowest-priority."""
        evicted: list[str] = []
        count = self.store.get_active_count(request.card_id, request.session_id)
        if count <= self.policy.MAX_ACTIVE_MEMORIES:
            return evicted
        # Need all records (active) to score; store.get_all returns active only.
        current = self.store.get_all(request.card_id, request.session_id)
        result: MemoryRetentionResult = self.policy.decide_retention(
            current_active=current,
            new_entries=[],
            card_id=request.card_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            max_active=self.policy.MAX_ACTIVE_MEMORIES,
        )
        for mid in result.evicted_ids:
            self.store.set_status(
                request.card_id, request.session_id, mid,
                ActiveMemoryStatus.EVICTED.value,
                reason="evicted: 15-slot retention",
            )
            evicted.append(mid)
        if self.retention_store is not None:
            self.retention_store.log_retention(result)
        return evicted

    # ---- Legacy entry (kept for backward compat; no idempotency/receipt) ----
    def commit(
        self,
        plan: MemoryCommitPlan,
        card_id: str,
        session_id: str,
        quality_decision: QualityDecision,
    ) -> list[ActiveMemoryEntry]:
        """Legacy commit. Gate must accept. Use commit_request for formal path."""
        from ..contracts.quality_decision import assert_side_effects_allowed
        assert_side_effects_allowed(quality_decision)

        current = self.store.get_all(card_id, session_id)
        validation = self.policy.validate_commit_plan(plan, len(current))
        if not validation.valid:
            raise ValueError(f"Invalid memory plan: {validation.errors}")

        for mid in plan.resolved_active_ids:
            self.store.resolve(card_id, session_id, mid)
        for entry in plan.new_active_entries:
            self.store.upsert(card_id, session_id, entry)
        for entry in plan.updated_active_entries:
            self.store.upsert(card_id, session_id, entry)

        # Best-effort retention for legacy path too.
        count = self.store.get_active_count(card_id, session_id)
        if count > self.policy.MAX_ACTIVE_MEMORIES:
            current = self.store.get_all(card_id, session_id)
            result = self.policy.decide_retention(
                current_active=current, new_entries=[],
                card_id=card_id, session_id=session_id,
                max_active=self.policy.MAX_ACTIVE_MEMORIES,
            )
            for mid in result.evicted_ids:
                self.store.set_status(
                    card_id, session_id, mid,
                    ActiveMemoryStatus.EVICTED.value,
                    reason="evicted: 15-slot retention",
                )

        return self.store.get_all(card_id, session_id)

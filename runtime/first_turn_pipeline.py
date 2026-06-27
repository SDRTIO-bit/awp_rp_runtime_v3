"""First Turn Pipeline -- orchestrates the first formal RP turn execution.

Follows the exact commit order specified in P-First Turn Execution V1:
  Session Ready → Player Input → RoundSnapshot → Worldbook Retrieval
  → Director / Delegation / Dynamic Agents → Continuity Barrier
  → Suggestion Conflict Governance → FinalTurnBrief → Fake Writer
  → Quality Gate → State Proposal → CardState Commit → TurnRecord Commit
  → D6 Memory Curator → Memory Commit / No-op → FirstTurnReceipt
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from ..contracts.first_turn_request import FirstTurnRequest
from ..contracts.first_turn_context import (
    FirstTurnContext, OpeningContext, SessionBoundWorldbookRetrievalResult,
)
from ..contracts.first_turn_receipt import (
    FirstTurnReceipt, FirstTurnFailure, FirstTurnFailureCode,
)
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics
from ..contracts.card_state import CardState
from ..contracts.card_state_commit import (
    CardStateCommitRequest, CardStateCommitResult, CardStateCommitStatus,
)
from ..contracts.card_state_patch import CardStatePatch, CardStatePatchOperation, PatchOpType
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.turn_record import TurnRecord
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.state_update_proposal import StateUpdateProposal
from ..contracts.director_plan import DirectorPlan
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.writer_draft import WriterDraft
from ..contracts.memory_commit_plan import MemoryCommitPlan

from ..storage.interfaces import (
    CardStateStore, TurnRecordStore, RoundSnapshotStore, TraceStore,
)
from ..storage.card_session_interfaces import (
    CardSessionBindingStore, OpeningRecordStore, WorldbookBindingStore,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _ms_since(start: float) -> int:
    return int((time.time() - start) * 1000)


# ---------------------------------------------------------------------------
# Adapter protocols (injected, fake for this phase)
# ---------------------------------------------------------------------------

class DirectorAdapter(Protocol):
    """Protocol for Director that produces a plan from a RoundSnapshot."""
    def plan(self, snapshot: RoundSnapshot) -> tuple[DirectorPlan, dict, dict]:
        ...


class WriterAdapter(Protocol):
    """Protocol for Writer that produces candidate text from a FinalTurnBrief."""
    def write(self, brief: FinalTurnBrief, snapshot: RoundSnapshot) -> WriterDraft:
        ...


class ReviserAdapter(Protocol):
    """Protocol for Reviser that revises draft based on quality issues."""
    def revise(self, draft: WriterDraft, quality: QualityDecision,
               brief: FinalTurnBrief) -> WriterDraft:
        ...


class QualityGateAdapter(Protocol):
    """Protocol for Quality Gate that evaluates candidate text."""
    def check(self, candidate_text: str, snapshot: RoundSnapshot) -> QualityDecision:
        ...


class StateProposalAdapter(Protocol):
    """Protocol for State Proposal that generates state changes from text."""
    def propose(self, accepted_text: str, snapshot: RoundSnapshot) -> StateUpdateProposal:
        ...


class MemoryCurationAdapter(Protocol):
    """Protocol for D6 Memory Curation."""
    def curate(self, turn_record: TurnRecord, snapshot: RoundSnapshot,
               quality: QualityDecision) -> MemoryCommitPlan | None:
        ...


# ---------------------------------------------------------------------------
# First Turn Pipeline
# ---------------------------------------------------------------------------

class FirstTurnPipeline:
    """Orchestrates the first formal RP turn execution.

    Uses injected stores and adapters for testability.
    All adapters are fake in this phase.
    """

    def __init__(
        self,
        # Stores
        card_state_store: CardStateStore,
        turn_record_store: TurnRecordStore,
        round_snapshot_store: RoundSnapshotStore,
        trace_store: TraceStore,
        binding_store: CardSessionBindingStore,
        opening_store: OpeningRecordStore,
        worldbook_store: WorldbookBindingStore,
        # Adapters
        director_adapter: DirectorAdapter,
        writer_adapter: WriterAdapter,
        quality_adapter: QualityGateAdapter,
        state_proposal_adapter: StateProposalAdapter,
        # Optional
        reviser_adapter: ReviserAdapter | None = None,
        memory_curation_adapter: MemoryCurationAdapter | None = None,
    ):
        self._card_states = card_state_store
        self._turn_records = turn_record_store
        self._snapshots = round_snapshot_store
        self._traces = trace_store
        self._bindings = binding_store
        self._openings = opening_store
        self._worldbooks = worldbook_store
        self._director = director_adapter
        self._writer = writer_adapter
        self._quality = quality_adapter
        self._state_proposal = state_proposal_adapter
        self._reviser = reviser_adapter
        self._memory_curation = memory_curation_adapter

    def execute(
        self,
        request: FirstTurnRequest,
    ) -> tuple[FirstTurnReceipt | None, FirstTurnFailure | None, FirstTurnDiagnostics]:
        """Execute the first formal RP turn.

        Returns (receipt, failure, diagnostics).
        receipt is set on success, failure on error, diagnostics always.
        """
        diag = FirstTurnDiagnostics(
            diagnostics_id=_id("ftd", request.request_id),
            request_id=request.request_id,
            trace_id=request.trace_id,
            session_id=request.session_id,
        )
        t_start = time.time()

        # ── Step 1: Validate request ──────────────────────────────────────
        step_start = time.time()
        errors = request.validate()
        diag.step_timings_ms["validate_request"] = _ms_since(step_start)
        if errors:
            diag.validation_errors = errors
            diag.steps_failed.append("validate_request")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.VALIDATION_ERROR
            diag.failure_message = "; ".join(errors)
            return None, self._failure(request, FirstTurnFailureCode.VALIDATION_ERROR,
                                       "; ".join(errors), "validate_request", diag), diag
        diag.steps_completed.append("validate_request")

        # ── Step 2: Load session binding ──────────────────────────────────
        step_start = time.time()
        binding = self._bindings.load(request.session_id)
        diag.step_timings_ms["load_binding"] = _ms_since(step_start)
        if not binding:
            diag.steps_failed.append("load_binding")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.BINDING_NOT_FOUND
            diag.failure_message = f"No CardSessionBinding for session {request.session_id}"
            return None, self._failure(request, FirstTurnFailureCode.BINDING_NOT_FOUND,
                                       diag.failure_message, "load_binding", diag), diag
        diag.steps_completed.append("load_binding")

        # ── Step 3: Verify session is ready + binding matches ─────────────
        step_start = time.time()
        diag.session_status = binding.status
        diag.binding_card_version = binding.card_version
        diag.binding_source_hash = binding.source_hash

        if binding.status != "ready":
            diag.steps_failed.append("verify_session")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.SESSION_NOT_READY
            diag.failure_message = f"Session status is '{binding.status}', expected 'ready'"
            return None, self._failure(request, FirstTurnFailureCode.SESSION_NOT_READY,
                                       diag.failure_message, "verify_session", diag), diag

        if binding.logical_card_id != request.expected_logical_card_id:
            diag.steps_failed.append("verify_session")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.CARD_VERSION_MISMATCH
            diag.failure_message = (
                f"logicalCardId mismatch: binding={binding.logical_card_id}, "
                f"request={request.expected_logical_card_id}"
            )
            return None, self._failure(request, FirstTurnFailureCode.CARD_VERSION_MISMATCH,
                                       diag.failure_message, "verify_session", diag), diag

        if binding.card_version != request.expected_card_version:
            diag.steps_failed.append("verify_session")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.CARD_VERSION_MISMATCH
            diag.failure_message = (
                f"cardVersion mismatch: binding={binding.card_version}, "
                f"request={request.expected_card_version}"
            )
            return None, self._failure(request, FirstTurnFailureCode.CARD_VERSION_MISMATCH,
                                       diag.failure_message, "verify_session", diag), diag

        if binding.source_hash != request.expected_source_hash:
            diag.steps_failed.append("verify_session")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.SOURCE_HASH_MISMATCH
            diag.failure_message = (
                f"sourceHash mismatch: binding={binding.source_hash}, "
                f"request={request.expected_source_hash}"
            )
            return None, self._failure(request, FirstTurnFailureCode.SOURCE_HASH_MISMATCH,
                                       diag.failure_message, "verify_session", diag), diag

        diag.step_timings_ms["verify_session"] = _ms_since(step_start)
        diag.steps_completed.append("verify_session")

        # ── Step 4: Load OpeningRecord ────────────────────────────────────
        step_start = time.time()
        opening = self._openings.get_by_session(request.session_id)
        diag.step_timings_ms["load_opening"] = _ms_since(step_start)
        if not opening:
            diag.steps_failed.append("load_opening")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.OPENING_RECORD_NOT_FOUND
            diag.failure_message = f"No OpeningRecord for session {request.session_id}"
            return None, self._failure(request, FirstTurnFailureCode.OPENING_RECORD_NOT_FOUND,
                                       diag.failure_message, "load_opening", diag), diag
        diag.steps_completed.append("load_opening")

        opening_context = OpeningContext(
            opening_record_id=opening.opening_record_id,
            greeting_id=opening.greeting_id,
            safe_display_content=opening.safe_display_content,
            source_greeting_ref=opening.source_greeting_ref,
        )

        # ── Step 5: Load WorldbookBinding & retrieve ──────────────────────
        step_start = time.time()
        wb_binding = self._worldbooks.get_by_session(request.session_id)
        diag.step_timings_ms["load_worldbook"] = _ms_since(step_start)
        if not wb_binding:
            diag.steps_failed.append("load_worldbook")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.WORLDBOOK_BINDING_NOT_FOUND
            diag.failure_message = f"No WorldbookBinding for session {request.session_id}"
            return None, self._failure(request, FirstTurnFailureCode.WORLDBOOK_BINDING_NOT_FOUND,
                                       diag.failure_message, "load_worldbook", diag), diag
        diag.steps_completed.append("load_worldbook")

        # Deterministic worldbook retrieval
        step_start = time.time()
        wb_result = self._retrieve_worldbook(request, wb_binding, opening)
        diag.step_timings_ms["retrieve_worldbook"] = _ms_since(step_start)
        diag.worldbook_candidate_count = len(wb_result.candidate_entry_ids)
        diag.worldbook_activated_count = len(wb_result.activated_entry_ids)
        diag.worldbook_rejected_count = len(wb_result.rejected_entry_ids_with_reasons)
        diag.worldbook_deferred_count = len(wb_result.deferred_entry_ids)
        diag.worldbook_disabled_count = len(wb_result.disabled_entry_ids)
        diag.worldbook_budget_dropped_count = len(wb_result.budget_dropped_entry_ids)
        diag.steps_completed.append("retrieve_worldbook")

        # ── Step 6: Load CardState & build RoundSnapshot ──────────────────
        step_start = time.time()
        card_state = self._card_states.load(
            request.expected_logical_card_id, request.session_id
        )
        if not card_state:
            # Initialize if not exists
            card_state = self._card_states.initialize(
                request.expected_logical_card_id, request.session_id
            )

        snapshot = RoundSnapshot(
            snapshot_id=_id("snap", request.turn_id),
            trace_id=request.trace_id,
            card_id=request.expected_logical_card_id,
            session_id=request.session_id,
            base_card_state_revision=card_state.revision,
            card_state=card_state,
            player_input=request.player_input,
            recent_turn_records=[],  # First turn: no history
            active_worldbook_entries=[e for e in wb_result.activated_content],
            active_memories=[],  # First turn: no memories
            rag_recall=[],  # First turn: no RAG
            memory_recall_diagnostics=[],
            memory_budget_decision={"disposition": "noop", "reason": "first_turn_no_memory"},
            max_turn_history=5,
            max_active_memories=15,
            created_at=_now(),
        )
        self._snapshots.save(snapshot)
        diag.step_timings_ms["build_snapshot"] = _ms_since(step_start)
        diag.steps_completed.append("build_snapshot")

        # ── Step 7: Director / Delegation / Dynamic Agents ────────────────
        step_start = time.time()
        director_plan, tool_plan, delegation_plan = self._director.plan(snapshot)

        # Build FinalTurnBrief (simplified: no tool gateway in this phase)
        brief = FinalTurnBrief(
            brief_id=_id("ftb", request.turn_id),
            turn_goal=director_plan.turn_goal,
            scene_focus=director_plan.scene_focus,
            must_preserve_facts=director_plan.must_preserve_facts,
            must_not_do=director_plan.must_not_do,
            writer_constraints=director_plan.writer_constraints,
            active_character_refs=director_plan.active_character_refs,
            narrative_opportunities=director_plan.narrative_opportunities,
            # First turn: no agent enrichments (all empty)
            accepted_history_findings=[],
            history_continuity_warnings=[],
            accepted_opportunities=[],
            accepted_world_life_candidates=[],
            accepted_relationship_findings=[],
            accepted_continuity_constraints=[],
        )

        # Dynamic agents: all not_required for first turn (empty history/memory)
        diag.agent_dispositions = {
            "history-recall": "not_required",
            "opportunity": "not_required",
            "world-life": "not_required",
            "emotion-relationship": "not_required",
            "continuity": "not_required",
        }
        diag.step_timings_ms["director_and_agents"] = _ms_since(step_start)
        diag.steps_completed.append("director_and_agents")

        # ── Step 8: Writer → Quality Gate ─────────────────────────────────
        step_start = time.time()
        writer_draft = self._writer.write(brief, snapshot)
        candidate_text = writer_draft.text if hasattr(writer_draft, 'text') else str(writer_draft)

        quality_decision = self._quality.check(candidate_text, snapshot)
        diag.quality_verdict = quality_decision.verdict.value
        diag.quality_blocking_reasons = list(quality_decision.blocking_reasons)
        diag.step_timings_ms["writer_and_quality"] = _ms_since(step_start)
        diag.steps_completed.append("writer_and_quality")

        # Quality reject → zero side effects
        if not quality_decision.allows_side_effects():
            diag.steps_failed.append("quality_gate")
            diag.outcome = "quality_rejected"
            diag.failure_code = FirstTurnFailureCode.QUALITY_REJECTED
            diag.failure_message = (
                f"Quality gate rejected: {quality_decision.blocking_reasons}"
            )
            receipt = FirstTurnReceipt(
                receipt_id=_id("ftr", request.request_id),
                request_id=request.request_id,
                workflow_run_id=request.workflow_run_id,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                attempt_id=request.attempt_id,
                session_id=request.session_id,
                logical_card_id=request.expected_logical_card_id,
                card_version=request.expected_card_version,
                source_hash=request.expected_source_hash,
                quality_verdict="reject",
                idempotency_status="new",
                created_at=_now(),
            )
            return receipt, None, diag

        diag.steps_completed.append("quality_gate")

        # ── Step 9: State Proposal → CardState Commit ─────────────────────
        step_start = time.time()
        state_proposal = self._state_proposal.propose(candidate_text, snapshot)

        # Build patch from proposal
        patch = CardStatePatch(
            patch_id=_id("patch", request.turn_id),
            card_id=request.expected_logical_card_id,
            session_id=request.session_id,
            trace_id=request.trace_id,
            operations=[
                CardStatePatchOperation(
                    op=PatchOpType(op_entry.op) if hasattr(op_entry, 'op') else PatchOpType.SET,
                    path=op_entry.path if hasattr(op_entry, 'path') else "",
                    value=op_entry.value if hasattr(op_entry, 'value') else None,
                )
                for op_entry in (state_proposal.operations if hasattr(state_proposal, 'operations') else [])
            ],
        )

        commit_request = CardStateCommitRequest(
            expected_revision=card_state.revision,
            patch=patch,
        )

        # Create the new state with incremented revision
        new_state = CardState(
            card_id=card_state.card_id,
            session_id=card_state.session_id,
            revision=card_state.revision + 1,
            variables=dict(card_state.variables),
            event_flags=dict(card_state.event_flags),
            scene_state=card_state.scene_state,
            created_at=card_state.created_at,
            updated_at=_now(),
        )

        state_result = self._card_states.commit(commit_request, new_state)
        diag.card_state_commit_status = state_result.status.value
        diag.step_timings_ms["state_commit"] = _ms_since(step_start)

        if state_result.status != CardStateCommitStatus.ACCEPTED:
            diag.steps_failed.append("state_commit")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.STATE_COMMIT_FAILED
            diag.failure_message = f"CardState commit failed: {state_result.error_message}"
            return None, self._failure(request, FirstTurnFailureCode.STATE_COMMIT_FAILED,
                                       diag.failure_message, "state_commit", diag), diag
        diag.steps_completed.append("state_commit")

        base_revision = card_state.revision
        result_revision = state_result.to_revision

        # ── Step 10: TurnRecord Commit ────────────────────────────────────
        step_start = time.time()
        turn_record = TurnRecord(
            turn_id=request.turn_id,
            trace_id=request.trace_id,
            session_id=request.session_id,
            card_id=request.expected_logical_card_id,
            turn_index=self._turn_records.get_next_turn_index(
                request.expected_logical_card_id, request.session_id
            ),
            player_input=request.player_input,
            writer_output=candidate_text,
            mode="normal",
            base_card_state_revision=base_revision,
            result_card_state_revision=result_revision,
            quality_decision_ref=request.turn_id,
            round_snapshot_ref=snapshot.snapshot_id,
            state_commit_ref=patch.patch_id,
            created_at=_now(),
        )

        try:
            self._turn_records.save(turn_record)
            diag.turn_record_commit_status = "committed"
        except Exception as e:
            diag.turn_record_commit_status = "failed"
            diag.steps_failed.append("turn_commit")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.TURN_COMMIT_FAILED
            diag.failure_message = f"TurnRecord commit failed: {e}"
            return None, self._failure(request, FirstTurnFailureCode.TURN_COMMIT_FAILED,
                                       diag.failure_message, "turn_commit", diag), diag

        diag.step_timings_ms["turn_commit"] = _ms_since(step_start)
        diag.steps_completed.append("turn_commit")

        # ── Step 11: D6 Memory Curation ───────────────────────────────────
        step_start = time.time()
        memory_status = "noop"
        active_write_count = 0
        rag_write_count = 0

        if self._memory_curation:
            mem_plan = self._memory_curation.curate(turn_record, snapshot, quality_decision)
            if mem_plan and mem_plan.active_entries:
                memory_status = "curated"
                active_write_count = len(mem_plan.active_entries)
                rag_write_count = len(mem_plan.rag_entries) if hasattr(mem_plan, 'rag_entries') else 0
            else:
                memory_status = "noop"
                diag.memory_curation_reason = "first_turn_no_memory_candidates"
        else:
            diag.memory_curation_reason = "no_memory_curation_adapter"

        diag.memory_curation_status = memory_status
        diag.step_timings_ms["memory_curation"] = _ms_since(step_start)
        diag.steps_completed.append("memory_curation")

        # ── Step 12: Build receipt ────────────────────────────────────────
        diag.outcome = "success"
        diag.step_timings_ms["total"] = _ms_since(t_start)

        receipt = FirstTurnReceipt(
            receipt_id=_id("ftr", request.request_id),
            request_id=request.request_id,
            workflow_run_id=request.workflow_run_id,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            logical_card_id=request.expected_logical_card_id,
            card_version=request.expected_card_version,
            source_hash=request.expected_source_hash,
            accepted_text=candidate_text[:200],  # Truncated for receipt
            quality_verdict="accept",
            base_card_state_revision=base_revision,
            result_card_state_revision=result_revision,
            card_state_commit_status="accepted",
            turn_record_id=turn_record.turn_id,
            turn_index=turn_record.turn_index,
            turn_record_commit_status="committed",
            memory_curation_status=memory_status,
            active_memory_write_count=active_write_count,
            rag_memory_write_count=rag_write_count,
            idempotency_status="new",
            created_at=_now(),
        )

        return receipt, None, diag

    # ── Worldbook Retrieval ───────────────────────────────────────────────

    def _retrieve_worldbook(
        self,
        request: FirstTurnRequest,
        wb_binding: Any,
        opening: Any,
    ) -> SessionBoundWorldbookRetrievalResult:
        """Deterministic session-bound worldbook retrieval.

        Only reads from the current session's WorldbookBinding.
        Never reads from global card library or other sessions.
        """
        retrieval_id = _id("wbr", request.turn_id)
        max_budget = 4000
        used_budget = 0
        activated_ids = []
        activated_content = []
        rejected = {}
        deferred = list(wb_binding.deferred_entry_ids) if hasattr(wb_binding, 'deferred_entry_ids') else []
        disabled = list(wb_binding.disabled_entry_ids) if hasattr(wb_binding, 'disabled_entry_ids') else []
        budget_dropped = []
        candidates = []
        branch_selections = []
        chunk_parents = []

        # Get entries from binding
        entries = []
        if hasattr(wb_binding, 'entries'):
            entries = wb_binding.entries if isinstance(wb_binding.entries, list) else []

        # Get card worldbook entries from the binding's catalog reference
        # In a real implementation, we'd load from the card definition store
        # For now, we work with the entries embedded in the binding
        for entry_data in entries:
            if isinstance(entry_data, dict):
                entry_id = entry_data.get("entry_id", "")
                enabled = entry_data.get("enabled", True)
                constant = entry_data.get("constant", False)
                selective = entry_data.get("selective", False)
                content = entry_data.get("content", "")
                title = entry_data.get("title", "")
                keys = entry_data.get("keys", [])
                priority = entry_data.get("priority", 50)
            else:
                entry_id = getattr(entry_data, 'entry_id', '')
                enabled = getattr(entry_data, 'enabled', True)
                constant = getattr(entry_data, 'constant', False)
                selective = getattr(entry_data, 'selective', False)
                content = getattr(entry_data, 'content', '')
                title = getattr(entry_data, 'title', '')
                keys = getattr(entry_data, 'keys', [])
                priority = getattr(entry_data, 'priority', 50)

            if not entry_id:
                continue

            candidates.append(entry_id)

            # Disabled entries are not activated
            if not enabled:
                disabled.append(entry_id)
                rejected[entry_id] = "disabled"
                continue

            # Selective entries are deferred (require condition evaluation)
            if selective:
                deferred.append(entry_id)
                rejected[entry_id] = "deferred_selective"
                continue

            # Constant entries activate unconditionally (within budget)
            # Non-constant entries activate if keywords match
            content_len = len(content)
            if used_budget + content_len > max_budget:
                budget_dropped.append(entry_id)
                rejected[entry_id] = "budget_exceeded"
                continue

            # For first turn, constant entries always activate
            # Non-constant entries activate by default (deterministic mode)
            activated_ids.append(entry_id)
            activated_content.append({
                "entry_id": entry_id,
                "title": title,
                "content": content,
                "keys": keys,
                "priority": priority,
                "constant": constant,
            })
            used_budget += content_len

        return SessionBoundWorldbookRetrievalResult(
            retrieval_id=retrieval_id,
            session_id=request.session_id,
            worldbook_binding_id=wb_binding.worldbook_binding_id
            if hasattr(wb_binding, 'worldbook_binding_id') else "",
            candidate_entry_ids=candidates,
            activated_entry_ids=activated_ids,
            rejected_entry_ids_with_reasons=rejected,
            deferred_entry_ids=deferred,
            disabled_entry_ids=disabled,
            budget_dropped_entry_ids=budget_dropped,
            branch_selections=branch_selections,
            chunk_parent_entry_ids=chunk_parents,
            activated_content=activated_content,
            total_budget_used=used_budget,
            max_budget=max_budget,
            created_at=_now(),
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _failure(
        self,
        request: FirstTurnRequest,
        code: str,
        message: str,
        step: str,
        diag: FirstTurnDiagnostics,
    ) -> FirstTurnFailure:
        return FirstTurnFailure(
            failure_id=_id("ftf", request.request_id),
            request_id=request.request_id,
            workflow_run_id=request.workflow_run_id,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            failure_code=code,
            failure_message=message,
            failed_at_step=step,
            diagnostics=diag.to_dict(),
            created_at=_now(),
        )

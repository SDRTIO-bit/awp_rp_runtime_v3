"""Persistent turn engine — shared execution core for the persistent nodes.

Encapsulates the real/fake Director → Writer → Quality → CardState commit
→ TurnRecord commit → D6 Memory Curator → Active/RAG memory commit pipeline
with a per-turn ExecutionTrace persisted to SqliteTraceStore.

Used by both AWPV2PersistentFirstTurn and AWPV2PersistentContinuationTurn so
the two nodes share one auditable code path. The nodes differ only in how
they assemble the RoundSnapshot (first turn: empty history; continuation:
via SessionRuntimeLoad).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.card_state import CardState
from ..contracts.card_state_commit import (
    CardStateCommitRequest, CardStateCommitStatus,
)
from ..contracts.card_state_patch import CardStatePatch
from ..contracts.turn_record import TurnRecord, TurnMode
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.writer_draft import WriterDraft
from ..contracts.writer_input_bundle import WriterInputBundle
from ..contracts.first_turn_receipt import FirstTurnReceipt
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics
from ..contracts.execution_trace import ExecutionTrace, TraceEvent
from ..contracts.memory_commit_plan import (
    MemoryCommitRequest, MemoryCommitStatus,
)

from .provider_adapter_factory import (
    DirectorAdapterFactory, WriterAdapterFactory,
    run_director, run_writer, AdapterOutcome,
)
from .writer_input_bundle_v2_builder import WriterInputBundleV2Builder
from .memory_curation_runtime import MemoryCurationRuntime
from .memory_plan_compiler import MemoryPlanCompiler
from .active_memory_commit_runtime import ActiveMemoryCommitRuntime
from .rag_memory_commit_runtime import RagMemoryCommitRuntime


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _ms_since(start: float) -> int:
    import time
    return int((time.time() - start) * 1000)


def _add_trace_event(
    trace: ExecutionTrace,
    event_type: str,
    actor: str,
    success: bool,
    duration_ms: int = 0,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    trace.add_event(TraceEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        event_type=event_type,
        timestamp=_now(),
        actor=actor,
        duration_ms=duration_ms,
        details=details or {},
        success=success,
        error=error,
    ))


def _plan_hash(plan: Any) -> str:
    """Stable short hash of a DirectorPlan for trace evidence (no raw content)."""
    try:
        blob = plan.to_dict() if hasattr(plan, "to_dict") else str(plan)
    except Exception:
        blob = str(plan)
    return hashlib.sha256(str(blob).encode("utf-8")).hexdigest()[:16]


class PersistentTurnEngine:
    """Runs one accepted turn with full evidence capture.

    The caller provides a RoundSnapshot already assembled (by the node).
    Returns a populated (receipt, context, diagnostics, card_state,
    turn_record, round_snapshot) tuple, mirroring the node RETURN contract.
    """

    def __init__(self, registry, profile: str = "production"):
        self._registry = registry
        self._profile = profile

    def execute(
        self,
        *,
        session_id: str,
        player_input: str,
        binding: Any,
        snapshot: RoundSnapshot,
        card_state: CardState,
        turn_id: str,
        attempt_id: str,
        request_id: str,
        workflow_run_id: str,
        trace_id: str,
        director_profile_id: str,
        writer_profile_id: str,
        turn_kind: str,
    ) -> tuple[dict, dict, dict, dict, dict, dict]:
        import time
        now = _now()
        t_start = time.time()

        diag = FirstTurnDiagnostics(
            diagnostics_id=_id("ptd", request_id),
            request_id=request_id, trace_id=trace_id,
            session_id=session_id,
            director_profile_id=director_profile_id,
            writer_profile_id=writer_profile_id,
        )

        trace = ExecutionTrace(
            trace_id=trace_id, turn_id=turn_id,
            card_id=binding.logical_card_id, session_id=session_id,
        )

        # ── Capture memory-use evidence from the snapshot ───────────────
        diag.round_snapshot_id = snapshot.snapshot_id
        diag.l1_turn_ids_recalled = [t.turn_id for t in snapshot.recent_turn_records]
        diag.l2_memory_ids_recalled = [
            m.get("memory_id", "") for m in snapshot.active_memories if m.get("memory_id")
        ]
        diag.l3_memory_ids_recalled = [
            r.get("memory_id", "") for r in snapshot.rag_recall if r.get("memory_id")
        ]
        diag.worldbook_entry_ids_considered = [
            e.get("entry_id", e.get("id", "")) for e in snapshot.active_worldbook_entries
            if e.get("entry_id") or e.get("id")
        ]
        diag.worldbook_entry_ids_activated = list(diag.worldbook_entry_ids_considered)
        diag.card_state_revision_before = card_state.revision

        _add_trace_event(trace, "round_snapshot", "round_snapshot_builder",
                         success=True, details={
                             "snapshot_id": snapshot.snapshot_id,
                             "l1_turn_ids_recalled": diag.l1_turn_ids_recalled,
                             "l2_memory_ids_recalled": diag.l2_memory_ids_recalled,
                             "l3_memory_ids_recalled": diag.l3_memory_ids_recalled,
                             "worldbook_entry_ids_activated": diag.worldbook_entry_ids_activated,
                         })
        diag.steps_completed.append("round_snapshot")

        # ── Director ─────────────────────────────────────────────────────
        step_start = time.time()
        dir_adapter, dir_outcome = DirectorAdapterFactory.build(director_profile_id)
        diag.director_provider_type = dir_outcome.provider
        diag.director_model = dir_outcome.model

        if not dir_outcome.built:
            diag.director_failure_code = dir_outcome.failure_code
            diag.steps_failed.append("director")
            diag.outcome = "failure"
            diag.failure_code = "DIRECTOR_" + dir_outcome.failure_code
            diag.failure_message = dir_outcome.failure_message
            _add_trace_event(trace, "director", "director", success=False,
                             duration_ms=_ms_since(step_start),
                             error=dir_outcome.failure_message,
                             details={"failure_code": dir_outcome.failure_code,
                                      "profile_id": director_profile_id,
                                      "provider": dir_outcome.provider})
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, card_state, snapshot)

        director_plan, dir_receipt = run_director(
            dir_adapter, dir_outcome, snapshot,
            workflow_run_id, trace_id, turn_id, attempt_id,
        )
        if director_plan is None:
            fc = dir_receipt.get("failure_code", "DIRECTOR_FAILED")
            diag.director_failure_code = fc
            diag.director_call_success = False
            diag.steps_failed.append("director")
            diag.outcome = "failure"
            diag.failure_code = "DIRECTOR_" + fc
            diag.failure_message = dir_receipt.get("failure_message", "director failed")
            _add_trace_event(trace, "director", "director", success=False,
                             duration_ms=_ms_since(step_start),
                             error=diag.failure_message,
                             details={"failure_code": fc, "provider": dir_outcome.provider})
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, card_state, snapshot)

        diag.director_call_success = True
        diag.director_plan_ref = getattr(director_plan, "plan_id", "") or _plan_hash(director_plan)
        brief = FinalTurnBrief(
            brief_id=_id("ftb", turn_id),
            trace_id=trace_id, snapshot_id=snapshot.snapshot_id,
            card_id=binding.logical_card_id, session_id=session_id,
            base_card_state_revision=snapshot.base_card_state_revision,
            turn_goal=director_plan.turn_goal,
            scene_focus=director_plan.scene_focus,
            must_preserve_facts=director_plan.must_preserve_facts,
            must_not_do=director_plan.must_not_do,
            writer_constraints=director_plan.writer_constraints,
            active_character_refs=director_plan.active_character_refs,
            narrative_opportunities=director_plan.narrative_opportunities,
        )
        _add_trace_event(trace, "director", "director", success=True,
                         duration_ms=_ms_since(step_start),
                         details={"plan_ref": diag.director_plan_ref,
                                  "provider": dir_outcome.provider,
                                  "model": dir_outcome.model})
        diag.steps_completed.append("director")

        # ── Writer ───────────────────────────────────────────────────────
        step_start = time.time()
        wrt_adapter, wrt_outcome = WriterAdapterFactory.build(writer_profile_id)
        diag.writer_provider_type = wrt_outcome.provider
        diag.writer_model = wrt_outcome.model

        if not wrt_outcome.built:
            diag.writer_failure_code = wrt_outcome.failure_code
            diag.steps_failed.append("writer")
            diag.outcome = "failure"
            diag.failure_code = "WRITER_" + wrt_outcome.failure_code
            diag.failure_message = wrt_outcome.failure_message
            _add_trace_event(trace, "writer", "writer", success=False,
                             duration_ms=_ms_since(step_start),
                             error=wrt_outcome.failure_message,
                             details={"failure_code": wrt_outcome.failure_code})
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, card_state, snapshot)

        bundle = WriterInputBundleV2Builder().build(snapshot, brief)
        candidate_text, wrt_receipt = run_writer(
            wrt_adapter, wrt_outcome, bundle,
            workflow_run_id, trace_id, turn_id, attempt_id,
            snapshot=snapshot,
        )
        if not candidate_text.strip():
            fc = wrt_receipt.get("failure_code", "WRITER_FAILED")
            diag.writer_failure_code = fc
            diag.writer_call_success = False
            diag.steps_failed.append("writer")
            diag.outcome = "failure"
            diag.failure_code = "WRITER_" + fc
            diag.failure_message = wrt_receipt.get("failure_message", "writer produced empty text")
            _add_trace_event(trace, "writer", "writer", success=False,
                             duration_ms=_ms_since(step_start),
                             error=diag.failure_message,
                             details={"failure_code": fc})
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, card_state, snapshot)

        diag.writer_call_success = True
        _add_trace_event(trace, "writer", "writer", success=True,
                         duration_ms=_ms_since(step_start),
                         details={"text_length": len(candidate_text),
                                  "provider": wrt_outcome.provider,
                                  "model": wrt_outcome.model})
        diag.steps_completed.append("writer")

        # ── Quality Gate (deterministic, non-LLM) ────────────────────────
        step_start = time.time()
        quality_decision = self._quality_check(candidate_text, snapshot, trace_id)
        diag.quality_verdict = quality_decision.verdict.value
        diag.quality_blocking_reasons = list(quality_decision.blocking_reasons)
        _add_trace_event(trace, "quality_gate", "quality_pipeline", success=True,
                         duration_ms=_ms_since(step_start),
                         details={"verdict": quality_decision.verdict.value,
                                  "overall_score": quality_decision.overall_score,
                                  "blocking_reasons": quality_decision.blocking_reasons})
        diag.steps_completed.append("quality_gate")

        if not quality_decision.allows_side_effects():
            diag.steps_failed.append("quality_gate")
            diag.outcome = "quality_rejected"
            diag.failure_message = f"Quality gate rejected: {quality_decision.blocking_reasons}"
            receipt = FirstTurnReceipt(
                receipt_id=_id("ptr", request_id),
                request_id=request_id, workflow_run_id=workflow_run_id,
                trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
                session_id=session_id,
                logical_card_id=binding.logical_card_id,
                card_version=binding.card_version,
                source_hash=binding.source_hash,
                quality_verdict="reject", idempotency_status="new",
                created_at=now,
            )
            self._persist_trace(trace, diag)
            return (receipt.to_dict(), {}, diag.to_dict(),
                    card_state.to_dict(), {}, snapshot.to_dict())

        # ── CardState Commit ─────────────────────────────────────────────
        step_start = time.time()
        patch = CardStatePatch(
            patch_id=_id("patch", turn_id),
            card_id=binding.logical_card_id, session_id=session_id,
            trace_id=trace_id, operations=[],
        )
        commit_request = CardStateCommitRequest(
            expected_revision=card_state.revision, patch=patch,
        )
        new_state = CardState(
            card_id=card_state.card_id, session_id=card_state.session_id,
            revision=card_state.revision + 1,
            variables=dict(card_state.variables),
            event_flags=dict(card_state.event_flags),
            scene_state=card_state.scene_state,
            created_at=card_state.created_at, updated_at=now,
        )
        state_result = self._registry.card_state_store.commit(commit_request, new_state)
        diag.card_state_commit_status = state_result.status.value
        _add_trace_event(trace, "card_state_commit", "card_state_store",
                         success=(state_result.status == CardStateCommitStatus.ACCEPTED),
                         duration_ms=_ms_since(step_start),
                         details={"status": state_result.status.value,
                                  "from_revision": card_state.revision,
                                  "to_revision": state_result.to_revision})

        if state_result.status != CardStateCommitStatus.ACCEPTED:
            diag.steps_failed.append("state_commit")
            diag.outcome = "failure"
            diag.failure_message = f"CardState commit failed: {state_result.error_message}"
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, new_state, snapshot)

        diag.steps_completed.append("state_commit")
        base_revision = card_state.revision
        result_revision = state_result.to_revision
        diag.card_state_revision_after = result_revision

        # ── TurnRecord Commit ────────────────────────────────────────────
        step_start = time.time()
        next_turn_index = self._registry.turn_record_store.get_next_turn_index(
            binding.logical_card_id, session_id
        )
        turn_record = TurnRecord(
            turn_id=turn_id, trace_id=trace_id,
            session_id=session_id, card_id=binding.logical_card_id,
            turn_index=next_turn_index,
            player_input=player_input, writer_output=candidate_text,
            mode=TurnMode.NORMAL,
            base_card_state_revision=base_revision,
            result_card_state_revision=result_revision,
            quality_decision_ref=turn_id,
            round_snapshot_ref=snapshot.snapshot_id,
            state_commit_ref=patch.patch_id,
            created_at=now, accepted_at=now,
        )
        try:
            self._registry.turn_record_store.save(turn_record)
            diag.turn_record_commit_status = "committed"
            diag.turn_record_id = turn_id
        except Exception as e:
            from ..storage.interfaces import DuplicateTurnError
            if isinstance(e, DuplicateTurnError):
                # Idempotent replay handled by the node BEFORE calling engine.
                # Reaching here means a race; surface as failure.
                diag.turn_record_commit_status = "failed"
                diag.steps_failed.append("turn_commit")
                diag.outcome = "failure"
                diag.failure_message = f"Duplicate turn: {e}"
                self._persist_trace(trace, diag)
                return self._failure_return(diag, trace, new_state, snapshot)
            diag.turn_record_commit_status = "failed"
            diag.steps_failed.append("turn_commit")
            diag.outcome = "failure"
            diag.failure_message = f"TurnRecord commit failed: {e}"
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, new_state, snapshot)

        _add_trace_event(trace, "turn_record_commit", "turn_record_store",
                         success=True, duration_ms=_ms_since(step_start),
                         details={"turn_id": turn_id, "turn_index": next_turn_index,
                                  "base_revision": base_revision,
                                  "result_revision": result_revision})
        diag.steps_completed.append("turn_commit")

        # ── D6 Memory Curator (real deterministic path, no silent noop) ──
        memory_status, active_ids, rag_ids, commit_ids = self._run_d6(
            turn_record, snapshot, quality_decision, result_revision,
            trace_id, turn_id, binding, trace,
        )
        diag.memory_curation_status = memory_status
        diag.active_memory_committed_ids = active_ids
        diag.rag_memory_committed_ids = rag_ids
        diag.memory_commit_ids = commit_ids
        diag.steps_completed.append("memory_curator")

        # ── Persist trace ────────────────────────────────────────────────
        diag.outcome = "success"
        self._persist_trace(trace, diag)

        receipt = FirstTurnReceipt(
            receipt_id=_id("ptr", request_id),
            request_id=request_id, workflow_run_id=workflow_run_id,
            trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
            session_id=session_id,
            logical_card_id=binding.logical_card_id,
            card_version=binding.card_version,
            source_hash=binding.source_hash,
            accepted_text=candidate_text[:200],
            quality_verdict="accept",
            base_card_state_revision=base_revision,
            result_card_state_revision=result_revision,
            card_state_commit_status="accepted",
            turn_record_id=turn_record.turn_id,
            turn_index=turn_record.turn_index,
            turn_record_commit_status="committed",
            memory_curation_status=memory_status,
            active_memory_write_count=len(active_ids),
            rag_memory_write_count=len(rag_ids),
            idempotency_status="fresh",
            created_at=now,
        )

        ctx = {
            "turn_id": turn_id,
            "turn_index": next_turn_index,
            "turn_kind": turn_kind,
            "session_id": session_id,
            "logical_card_id": binding.logical_card_id,
            "recent_accepted_turn_count": len(snapshot.recent_turn_records),
            "active_memory_count": len(snapshot.active_memories),
            "rag_recall_count": len(snapshot.rag_recall),
            "base_card_state_revision": base_revision,
            "result_card_state_revision": result_revision,
            "workflow_run_id": workflow_run_id,
            "trace_id": trace_id,
            "idempotency_status": "fresh",
            "director_provider": diag.director_provider_type,
            "writer_provider": diag.writer_provider_type,
            "created_at": now,
        }

        return (
            receipt.to_dict(), ctx, diag.to_dict(),
            new_state.to_dict(), turn_record.to_dict(), snapshot.to_dict(),
        )

    # ── Quality gate (deterministic, existing rules) ────────────────────
    def _quality_check(
        self, candidate_text: str, snapshot: RoundSnapshot, trace_id: str,
    ) -> QualityDecision:
        from .quality_pipeline_runtime import QualityPipelineRuntime
        from ..contracts.writer_draft import WriterDraft
        draft = WriterDraft(
            draft_id=f"qd_{uuid.uuid4().hex[:8]}",
            trace_id=trace_id, snapshot_id=snapshot.snapshot_id,
            text=candidate_text,
        )
        pipeline = QualityPipelineRuntime()
        return pipeline.check(draft, snapshot)

    # ── D6 memory curator → Active/RAG commit ───────────────────────────
    def _run_d6(
        self,
        turn_record: TurnRecord,
        snapshot: RoundSnapshot,
        quality_decision: QualityDecision,
        result_revision: int,
        trace_id: str,
        turn_id: str,
        binding: Any,
        trace: ExecutionTrace,
    ) -> tuple[str, list[str], list[str], list[str]]:
        import time
        step_start = time.time()
        active_ids: list[str] = []
        rag_ids: list[str] = []
        commit_ids: list[str] = []
        memory_status = "noop"

        # Use the deterministic D6 runtime + candidate generator (rule-based,
        # not the test-only fixture). This is the real curation path; it
        # produces candidates only when long-term signals are present.
        runtime = MemoryCurationRuntime()
        try:
            curation_result = runtime.curate(
                quality_decision=quality_decision,
                card_state_commit_result=None,
                turn_record=turn_record,
                snapshot=snapshot,
                trace=trace,
            )
        except Exception as e:
            _add_trace_event(trace, "memory_curator", "memory_curation_runtime",
                             success=False, duration_ms=_ms_since(step_start),
                             error=str(e)[:200])
            return "failed", active_ids, rag_ids, commit_ids

        if curation_result is None or not curation_result.accepted_candidates:
            _add_trace_event(trace, "memory_curator", "memory_curation_runtime",
                             success=True, duration_ms=_ms_since(step_start),
                             details={"status": "noop",
                                      "skip_reason": "no_long_term_signals"})
            return "noop", active_ids, rag_ids, commit_ids

        # Compile → commit
        compiler = MemoryPlanCompiler()
        plan = compiler.compile(
            curation_result, turn_id, binding.logical_card_id,
            turn_record.session_id, trace_id, result_revision,
            turn_record.quality_decision_ref or turn_id,
        )

        has_active = bool(plan.new_active_entries or plan.updated_active_entries)
        has_rag = bool(plan.new_rag_entries)

        if has_active:
            active_runtime = ActiveMemoryCommitRuntime(self._registry.active_memory_store)
            mem_request = MemoryCommitRequest(
                plan=plan,
                card_id=binding.logical_card_id, session_id=turn_record.session_id,
                turn_id=turn_id, trace_id=trace_id,
                memory_commit_id=plan.memory_commit_id,
                idempotency_key=plan.idempotency_key,
                quality_decision_ref=turn_id,
                expected_card_state_revision=result_revision,
                card_state_commit_success=True,
                turn_record_commit_success=True,
            )
            try:
                mem_result = active_runtime.commit_request(mem_request, quality_decision)
                if mem_result.status == MemoryCommitStatus.COMMITTED and mem_result.receipt:
                    active_ids = list(mem_result.receipt.committed_active_ids)
                    commit_ids.append(plan.memory_commit_id)
                    if memory_status == "noop":
                        memory_status = "curated_active"
                elif mem_result.status == MemoryCommitStatus.IDEMPOTENT_REPLAY and mem_result.receipt:
                    active_ids = list(mem_result.receipt.committed_active_ids)
                    if memory_status == "noop":
                        memory_status = "curated_active_replay"
                else:
                    if memory_status != "failed":
                        memory_status = f"active_blocked:{mem_result.status}"
            except Exception as e:
                memory_status = "failed"
                _add_trace_event(trace, "active_memory_commit", "active_memory_store",
                                 success=False, error=str(e)[:200])
                return memory_status, active_ids, rag_ids, commit_ids

        if has_rag:
            rag_runtime = RagMemoryCommitRuntime(self._registry.rag_memory_store)
            rag_request = MemoryCommitRequest(
                plan=plan,
                card_id=binding.logical_card_id, session_id=turn_record.session_id,
                turn_id=turn_id, trace_id=trace_id,
                memory_commit_id=f"rag_{plan.memory_commit_id}",
                idempotency_key=f"rag:{plan.idempotency_key}",
                quality_decision_ref=turn_id,
                expected_card_state_revision=result_revision,
                card_state_commit_success=True,
                turn_record_commit_success=True,
            )
            try:
                rag_result = rag_runtime.commit_request(rag_request, quality_decision)
                if rag_result.status == MemoryCommitStatus.COMMITTED and rag_result.receipt:
                    rag_ids = list(rag_result.receipt.committed_rag_ids)
                    commit_ids.append(f"rag_{plan.memory_commit_id}")
                    if memory_status in ("noop", "curated_active", "curated_active_replay"):
                        memory_status = "curated_both" if has_active else "curated_rag"
                elif rag_result.status == MemoryCommitStatus.IDEMPOTENT_REPLAY and rag_result.receipt:
                    rag_ids = list(rag_result.receipt.committed_rag_ids)
                    if memory_status in ("noop", "curated_active", "curated_active_replay"):
                        memory_status = "curated_both_replay" if has_active else "curated_rag_replay"
                else:
                    if not memory_status.startswith("failed"):
                        memory_status = f"rag_blocked:{rag_result.status}"
            except Exception as e:
                memory_status = "failed"
                _add_trace_event(trace, "rag_memory_commit", "rag_memory_store",
                                 success=False, error=str(e)[:200])
                return memory_status, active_ids, rag_ids, commit_ids

        _add_trace_event(trace, "memory_curator", "memory_curation_runtime",
                         success=(memory_status != "failed"),
                         duration_ms=_ms_since(step_start),
                         details={
                             "status": memory_status,
                             "active_committed_ids": active_ids,
                             "rag_committed_ids": rag_ids,
                             "commit_ids": commit_ids,
                             "total_accepted": curation_result.total_candidates_accepted,
                         })
        return memory_status, active_ids, rag_ids, commit_ids

    def _persist_trace(self, trace: ExecutionTrace, diag: FirstTurnDiagnostics) -> None:
        try:
            trace.total_duration_ms = sum(
                (e.duration_ms or 0) for e in trace.events
            )
            self._registry.trace_store.save(trace)
            diag.trace_persisted = True
        except Exception:
            # Trace persistence is non-fatal; the turn outcome already stands.
            diag.trace_persisted = False

    def _failure_return(
        self, diag: FirstTurnDiagnostics, trace: ExecutionTrace,
        card_state: CardState, snapshot: RoundSnapshot,
    ) -> tuple[dict, dict, dict, dict, dict, dict]:
        return ({}, {}, diag.to_dict(),
                card_state.to_dict() if card_state else {}, {}, snapshot.to_dict())

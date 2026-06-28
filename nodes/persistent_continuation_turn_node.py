"""AWPV2PersistentContinuationTurn — Turn 2+ using RuntimeStoreFactory + SQLite.

All history restored from SQLite via SessionRuntimeLoad + RoundSnapshotBuilder.
No dbPath input. No JSON injection. No Fake stores for state/turn/memory.
Uses RuntimeStoreFactory.from_env() for profile + namespace resolution.

Idempotent replay: same sessionId + turnId + requestId returns the existing
completed receipt without re-calling Provider or re-writing state.
"""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.card_state import CardState
from ..contracts.turn_record import TurnRecord, TurnMode
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.director_plan import DirectorPlan
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.writer_draft import WriterDraft
from ..contracts.state_update_proposal import StateUpdateProposal
from ..contracts.card_state_patch import CardStatePatch
from ..contracts.card_state_commit import CardStateCommitRequest, CardStateCommitStatus
from ..contracts.first_turn_receipt import FirstTurnReceipt
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics
from ..contracts.memory_commit_plan import MemoryCommitRequest, MemoryCommitStatus

from ..runtime.runtime_store_factory import RuntimeStoreFactory
from ..runtime.session_runtime_load import SessionRuntimeLoad
from ..runtime.active_memory_commit_runtime import ActiveMemoryCommitRuntime
from ..runtime.rag_memory_commit_runtime import RagMemoryCommitRuntime
from ..adapters.llm.model_profile_registry import ModelProfileRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _ms_since(start: float) -> int:
    return int((time.time() - start) * 1000)


class _FakeDirectorAdapter:
    def plan(self, snapshot: RoundSnapshot) -> tuple[DirectorPlan, dict, dict]:
        plan = DirectorPlan(
            turn_goal=f"Continue the narrative (turn {len(snapshot.recent_turn_records) + 1})",
            scene_focus="Ongoing scene",
            must_preserve_facts=[],
            must_not_do=["Do not contradict established facts"],
            narrative_opportunities=["Build on previous interactions"],
            unresolved_threads=[],
            risk_flags=[],
            writer_constraints=["Stay in character", "Maintain continuity"],
            active_character_refs=[],
        )
        return plan, {}, {}


class _FakeWriterAdapter:
    def write(self, brief: FinalTurnBrief, snapshot: RoundSnapshot) -> WriterDraft:
        history_count = len(snapshot.recent_turn_records)
        last_input = ""
        if snapshot.recent_turn_records:
            last_input = snapshot.recent_turn_records[0].player_input[:50]
        text = (
            f"[Turn {history_count + 1} Response] "
            f"Continuing from previous interaction. "
            f"Player said: '{snapshot.player_input}'. "
            f"Previous context: '{last_input}'. "
            f"The narrative builds on {brief.turn_goal}."
        )
        text += " " + "The story continues with depth and consistency." * 3
        return WriterDraft(
            draft_id=f"cont_draft_{history_count}",
            text=text,
        )


class _FakeQualityAdapter:
    def check(self, candidate_text: str, snapshot: RoundSnapshot) -> QualityDecision:
        blocking = []
        if len(candidate_text.strip()) < 50:
            blocking.append("Text too short (minimum 50 characters)")
        if "ERROR" in candidate_text:
            blocking.append("Contains error marker")
        if blocking:
            return QualityDecision(
                verdict=QualityVerdict.REJECTED,
                candidate_text=candidate_text,
                blocking_reasons=blocking,
            )
        return QualityDecision(
            verdict=QualityVerdict.ACCEPTED,
            candidate_text=candidate_text,
            overall_score=0.8,
        )


class _FakeStateProposalAdapter:
    def propose(self, accepted_text: str, snapshot: RoundSnapshot) -> StateUpdateProposal:
        return StateUpdateProposal(
            proposal_id=f"cont_proposal_{snapshot.snapshot_id[:12]}",
            patch_ops=[],
            reasoning="Continuation turn: no state changes needed",
        )


def _build_replayed_receipt(
    existing_record: TurnRecord,
    request_id: str,
    workflow_run_id: str,
    session_id: str,
    binding: Any,
    now: str,
) -> FirstTurnReceipt:
    """Build a replayed receipt from an existing TurnRecord."""
    return FirstTurnReceipt(
        receipt_id=_id("ctr_replay", request_id),
        request_id=request_id,
        workflow_run_id=workflow_run_id,
        trace_id=existing_record.trace_id,
        turn_id=existing_record.turn_id,
        attempt_id="",
        session_id=session_id,
        logical_card_id=binding.logical_card_id,
        card_version=binding.card_version,
        source_hash=binding.source_hash,
        accepted_text="",
        quality_verdict="accept",
        base_card_state_revision=existing_record.base_card_state_revision,
        result_card_state_revision=existing_record.result_card_state_revision,
        card_state_commit_status="accepted",
        turn_record_id=existing_record.turn_id,
        turn_index=existing_record.turn_index,
        turn_record_commit_status="committed",
        memory_curation_status="noop",
        idempotency_status="replayed",
        created_at=now,
    )


class AWPV2PersistentContinuationTurn:
    """Execute Turn 2+ using RuntimeStoreFactory + SQLite.

    Key changes from previous version:
    - NO db_path input
    - Uses RuntimeStoreFactory.from_env() for profile + namespace
    - Memory commit via test fixture (test profile) or no-op (production)
    - RoundSnapshotBuilder is the canonical context entry point
    - Idempotent replay: DuplicateTurnError → replayed receipt
    - Model profiles: director_profile_id / writer_profile_id replace free strings
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "session_id": ("STRING", {"default": ""}),
                "player_input": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                "workflow_run_id": ("STRING", {"default": ""}),
                "trace_id": ("STRING", {"default": ""}),
                "turn_id": ("STRING", {"default": ""}),
                "attempt_id": ("STRING", {"default": ""}),
                "request_id": ("STRING", {"default": ""}),
                "run_id": ("STRING", {"default": ""}),
                "director_profile_id": ("STRING", {"default": "fake-director"}),
                "writer_profile_id": ("STRING", {"default": "fake-writer"}),
            },
        }

    RETURN_TYPES = (
        "FIRST_TURN_RECEIPT", "JSON", "FIRST_TURN_DIAGNOSTICS",
        "CARD_STATE", "TURN_RECORD", "ROUND_SNAPSHOT",
    )
    RETURN_NAMES = (
        "receipt", "continuation_context", "diagnostics",
        "card_state", "turn_record", "round_snapshot",
    )
    FUNCTION = "execute"
    CATEGORY = "AWP V2/Persistent Runtime"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return time.time()

    def execute(
        self,
        session_id: str,
        player_input: str,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
        request_id: str = "",
        run_id: str = "",
        director_profile_id: str = "fake-director",
        writer_profile_id: str = "fake-writer",
    ) -> tuple:
        now = _now()
        seed = f"{session_id}:{now}:{run_id}"

        if not request_id:
            request_id = f"ctr_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
        if not workflow_run_id:
            workflow_run_id = f"wfr_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
        if not trace_id:
            trace_id = f"trc_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
        if not turn_id:
            turn_id = f"turn_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
        if not attempt_id:
            attempt_id = f"att_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"

        # ── Validate model profiles ──────────────────────────────────────
        try:
            dir_profile = ModelProfileRegistry.resolve(director_profile_id)
        except ValueError as e:
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ctd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id,
                outcome="failure",
                failure_message=str(e),
                steps_failed=["model_profile_validation"],
            )
            return ({}, {}, diag.to_dict(), {}, {}, {})

        try:
            wrt_profile = ModelProfileRegistry.resolve(writer_profile_id)
        except ValueError as e:
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ctd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id,
                outcome="failure",
                failure_message=str(e),
                steps_failed=["model_profile_validation"],
            )
            return ({}, {}, diag.to_dict(), {}, {}, {})

        # ── Resolve factory from env ─────────────────────────────────────
        factory = RuntimeStoreFactory.from_env()
        registry = factory.registry

        # ── IDEMPOTENT REPLAY CHECK ──────────────────────────────────────
        existing_record = registry.turn_record_store.load(turn_id)
        if existing_record is not None:
            # Turn already completed — verify it belongs to this session
            if existing_record.session_id != session_id:
                diag = FirstTurnDiagnostics(
                    diagnostics_id=_id("ctd", request_id),
                    request_id=request_id, trace_id=trace_id,
                    session_id=session_id,
                    outcome="failure",
                    failure_message=(
                        f"Turn '{turn_id}' belongs to session "
                        f"'{existing_record.session_id}', not '{session_id}'"
                    ),
                    steps_failed=["session_binding_conflict"],
                )
                return ({}, {}, diag.to_dict(), {}, {}, {})

            # Load binding for the replayed receipt
            binding = registry.card_session_binding_store.load(session_id)
            if not binding:
                diag = FirstTurnDiagnostics(
                    diagnostics_id=_id("ctd", request_id),
                    request_id=request_id, trace_id=trace_id,
                    session_id=session_id,
                    outcome="failure",
                    failure_message=f"No CardSessionBinding for session {session_id}",
                    steps_failed=["session_load"],
                )
                return ({}, {}, diag.to_dict(), {}, {}, {})

            cs = registry.card_state_store.load(binding.logical_card_id, session_id)

            replayed_receipt = _build_replayed_receipt(
                existing_record, request_id, workflow_run_id,
                session_id, binding, now,
            )

            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ctd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id,
                outcome="success",
                steps_completed=["idempotent_replay"],
                agent_dispositions={"replay": "replayed"},
                turn_record_commit_status="replayed",
                card_state_commit_status="replayed",
            )
            diag.step_timings_ms["total"] = 0

            cont_ctx = {
                "turn_id": existing_record.turn_id,
                "turn_index": existing_record.turn_index,
                "turn_kind": "continuation",
                "session_id": session_id,
                "logical_card_id": binding.logical_card_id,
                "idempotency_status": "replayed",
                "created_at": now,
            }

            return (
                replayed_receipt.to_dict(),
                cont_ctx,
                diag.to_dict(),
                cs.to_dict() if cs else {},
                existing_record.to_dict(),
                {},
            )

        # ── Load from persistent stores via SessionRuntimeLoad ───────────
        loader = SessionRuntimeLoad(registry)
        bundle = loader.load(
            session_id=session_id,
            player_input=player_input,
        )

        diag = FirstTurnDiagnostics(
            diagnostics_id=_id("ctd", request_id),
            request_id=request_id,
            trace_id=trace_id,
            session_id=session_id,
        )
        t_start = time.time()

        if not bundle.is_valid:
            diag.outcome = "failure"
            diag.failure_message = "; ".join(bundle.load_errors)
            diag.steps_failed.append("session_load")
            return ({}, {}, diag.to_dict(), {}, {}, {})

        snapshot = bundle.round_snapshot
        cs = bundle.card_state
        binding = bundle.card_session_binding

        diag.step_timings_ms["session_load"] = _ms_since(t_start)
        diag.steps_completed.append("session_load")

        diag.agent_dispositions = {
            "history-recall": "loaded" if bundle.l1_turn_count > 0 else "empty",
            "active-memory": "loaded" if bundle.l2_active_memory_count > 0 else "empty",
            "rag-memory": "loaded" if bundle.l3_rag_recall_count > 0 else "empty",
        }

        # ── Director ────────────────────────────────────────────────────
        step_start = time.time()
        dir_adapter = _FakeDirectorAdapter()
        director_plan, _, _ = dir_adapter.plan(snapshot)

        brief = FinalTurnBrief(
            brief_id=_id("ftb", turn_id),
            turn_goal=director_plan.turn_goal,
            scene_focus=director_plan.scene_focus,
            must_preserve_facts=director_plan.must_preserve_facts,
            must_not_do=director_plan.must_not_do,
            writer_constraints=director_plan.writer_constraints,
            active_character_refs=director_plan.active_character_refs,
            narrative_opportunities=director_plan.narrative_opportunities,
            accepted_history_findings=[],
            history_continuity_warnings=[],
            accepted_opportunities=[],
            accepted_world_life_candidates=[],
            accepted_relationship_findings=[],
            accepted_continuity_constraints=[],
        )
        diag.step_timings_ms["director_and_agents"] = _ms_since(step_start)
        diag.steps_completed.append("director_and_agents")

        # ── Writer → Quality ────────────────────────────────────────────
        step_start = time.time()
        wrt_adapter = _FakeWriterAdapter()
        writer_draft = wrt_adapter.write(brief, snapshot)
        candidate_text = writer_draft.text

        quality_adapter = _FakeQualityAdapter()
        quality_decision = quality_adapter.check(candidate_text, snapshot)
        diag.quality_verdict = quality_decision.verdict.value
        diag.quality_blocking_reasons = list(quality_decision.blocking_reasons)
        diag.step_timings_ms["writer_and_quality"] = _ms_since(step_start)
        diag.steps_completed.append("writer_and_quality")

        if not quality_decision.allows_side_effects():
            diag.steps_failed.append("quality_gate")
            diag.outcome = "quality_rejected"
            diag.failure_message = f"Quality gate rejected: {quality_decision.blocking_reasons}"
            receipt = FirstTurnReceipt(
                receipt_id=_id("ctr", request_id),
                request_id=request_id, workflow_run_id=workflow_run_id,
                trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
                session_id=session_id,
                logical_card_id=binding.logical_card_id,
                card_version=binding.card_version,
                source_hash=binding.source_hash,
                quality_verdict="reject", idempotency_status="new",
                created_at=now,
            )
            return (receipt.to_dict(), {}, diag.to_dict(), cs.to_dict(), {}, {})

        diag.steps_completed.append("quality_gate")

        # ── CardState Commit ────────────────────────────────────────────
        step_start = time.time()
        patch = CardStatePatch(
            patch_id=_id("patch", turn_id),
            card_id=binding.logical_card_id,
            session_id=session_id,
            trace_id=trace_id,
            operations=[],
        )
        commit_request = CardStateCommitRequest(
            expected_revision=cs.revision,
            patch=patch,
        )
        new_state = CardState(
            card_id=cs.card_id, session_id=cs.session_id,
            revision=cs.revision + 1,
            variables=dict(cs.variables),
            event_flags=dict(cs.event_flags),
            scene_state=cs.scene_state,
            created_at=cs.created_at, updated_at=now,
        )
        state_result = registry.card_state_store.commit(commit_request, new_state)
        diag.card_state_commit_status = state_result.status.value
        diag.step_timings_ms["state_commit"] = _ms_since(step_start)

        if state_result.status != CardStateCommitStatus.ACCEPTED:
            diag.steps_failed.append("state_commit")
            diag.outcome = "failure"
            diag.failure_message = f"CardState commit failed: {state_result.error_message}"
            return ({}, {}, diag.to_dict(), cs.to_dict(), {}, {})

        diag.steps_completed.append("state_commit")
        base_revision = cs.revision
        result_revision = state_result.to_revision

        # ── TurnRecord Commit ───────────────────────────────────────────
        step_start = time.time()
        next_turn_index = registry.turn_record_store.get_next_turn_index(
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
            created_at=now,
        )
        try:
            registry.turn_record_store.save(turn_record)
            diag.turn_record_commit_status = "committed"
        except Exception as e:
            # Idempotent replay: DuplicateTurnError → return existing receipt
            from ..storage.interfaces import DuplicateTurnError
            if isinstance(e, DuplicateTurnError):
                existing = registry.turn_record_store.load(turn_id)
                if existing:
                    replayed_receipt = _build_replayed_receipt(
                        existing, request_id, workflow_run_id,
                        session_id, binding, now,
                    )
                    diag.turn_record_commit_status = "replayed"
                    diag.card_state_commit_status = "replayed"
                    diag.outcome = "success"
                    diag.steps_completed.append("idempotent_replay")
                    diag.step_timings_ms["total"] = _ms_since(t_start)

                    cont_ctx = {
                        "turn_id": existing.turn_id,
                        "turn_index": existing.turn_index,
                        "turn_kind": "continuation",
                        "session_id": session_id,
                        "logical_card_id": binding.logical_card_id,
                        "idempotency_status": "replayed",
                        "created_at": now,
                    }

                    return (
                        replayed_receipt.to_dict(),
                        cont_ctx,
                        diag.to_dict(),
                        cs.to_dict(),
                        existing.to_dict(),
                        snapshot.to_dict(),
                    )

            diag.turn_record_commit_status = "failed"
            diag.steps_failed.append("turn_commit")
            diag.outcome = "failure"
            diag.failure_message = f"TurnRecord commit failed: {e}"
            return ({}, {}, diag.to_dict(), cs.to_dict(), {}, {})

        diag.step_timings_ms["turn_commit"] = _ms_since(step_start)
        diag.steps_completed.append("turn_commit")

        # ── D6 Memory Curation ──────────────────────────────────────────
        step_start = time.time()
        memory_status = "noop"
        active_write_count = 0
        rag_write_count = 0

        try:
            from ..testing.fakes.test_memory_curator_fixture import compile_test_memory_plan
            plan = compile_test_memory_plan(turn_record, snapshot, quality_decision)
            if plan and (plan.new_active_entries or plan.new_rag_entries):
                if plan.new_active_entries:
                    active_runtime = ActiveMemoryCommitRuntime(registry.active_memory_store)
                    mem_request = MemoryCommitRequest(
                        plan=plan,
                        card_id=binding.logical_card_id,
                        session_id=session_id,
                        turn_id=turn_id,
                        trace_id=trace_id,
                        memory_commit_id=plan.memory_commit_id,
                        idempotency_key=plan.idempotency_key,
                        quality_decision_ref=turn_id,
                        expected_card_state_revision=result_revision,
                        card_state_commit_success=True,
                        turn_record_commit_success=True,
                    )
                    mem_result = active_runtime.commit_request(mem_request, quality_decision)
                    if mem_result.status == MemoryCommitStatus.COMMITTED:
                        active_write_count = len(plan.new_active_entries)
                        memory_status = "curated_active"

                if plan.new_rag_entries:
                    rag_runtime = RagMemoryCommitRuntime(registry.rag_memory_store)
                    rag_request = MemoryCommitRequest(
                        plan=plan,
                        card_id=binding.logical_card_id,
                        session_id=session_id,
                        turn_id=turn_id,
                        trace_id=trace_id,
                        memory_commit_id=f"rag_{plan.memory_commit_id}",
                        idempotency_key=f"rag:{plan.idempotency_key}",
                        quality_decision_ref=turn_id,
                        expected_card_state_revision=result_revision,
                        card_state_commit_success=True,
                        turn_record_commit_success=True,
                    )
                    rag_result = rag_runtime.commit_request(rag_request, quality_decision)
                    if rag_result.status == MemoryCommitStatus.COMMITTED:
                        rag_write_count = len(plan.new_rag_entries)
                        memory_status = "curated_both" if active_write_count > 0 else "curated_rag"
        except Exception:
            memory_status = "noop"

        diag.memory_curation_status = memory_status
        diag.step_timings_ms["memory_curation"] = _ms_since(step_start)
        diag.steps_completed.append("memory_curation")

        # ── Build receipt ───────────────────────────────────────────────
        diag.outcome = "success"
        diag.step_timings_ms["total"] = _ms_since(t_start)

        receipt = FirstTurnReceipt(
            receipt_id=_id("ctr", request_id),
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
            idempotency_status="fresh",
            created_at=now,
        )

        cont_ctx = {
            "turn_id": turn_id,
            "turn_index": next_turn_index,
            "turn_kind": "continuation",
            "session_id": session_id,
            "logical_card_id": binding.logical_card_id,
            "recent_accepted_turn_count": bundle.l1_turn_count,
            "active_memory_count": bundle.l2_active_memory_count,
            "rag_recall_count": bundle.l3_rag_recall_count,
            "base_card_state_revision": base_revision,
            "result_card_state_revision": result_revision,
            "workflow_run_id": workflow_run_id,
            "trace_id": trace_id,
            "idempotency_status": "fresh",
            "created_at": now,
        }

        return (
            receipt.to_dict(),
            cont_ctx,
            diag.to_dict(),
            new_state.to_dict(),
            turn_record.to_dict(),
            snapshot.to_dict(),
        )


NODE_CLASS_MAPPINGS = {
    "AWPV2PersistentContinuationTurn": AWPV2PersistentContinuationTurn,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2PersistentContinuationTurn": "AWP V2 Persistent Continuation Turn",
}

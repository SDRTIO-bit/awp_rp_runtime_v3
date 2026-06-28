"""AWPV2PersistentFirstTurn — Turn 1 using RuntimeStoreFactory + SQLite.

Replaces AWPV2FirstTurnExecution for the canonical persistent path.
All stores come from RuntimeStoreFactory. No Fake stores. No dbPath input.
Uses SessionRuntimeLoad + RoundSnapshotBuilder for context assembly.
Commits to SQLite: CardState, TurnRecord, D6 Memory (test fixture or no-op).

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
from ..contracts.card_state_commit import CardStateCommitRequest, CardStateCommitStatus
from ..contracts.card_state_patch import CardStatePatch
from ..contracts.turn_record import TurnRecord, TurnMode
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.director_plan import DirectorPlan
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.writer_draft import WriterDraft
from ..contracts.state_update_proposal import StateUpdateProposal
from ..contracts.first_turn_receipt import FirstTurnReceipt
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics
from ..contracts.memory_commit_plan import MemoryCommitRequest, MemoryCommitStatus

from ..runtime.runtime_store_factory import RuntimeStoreFactory
from ..runtime.session_runtime_load import SessionRuntimeLoad
from ..runtime.round_snapshot_builder import RoundSnapshotBuilder
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
            turn_goal="Begin the first interaction",
            scene_focus="Opening scene",
            must_preserve_facts=[],
            must_not_do=["Do not contradict the opening greeting"],
            narrative_opportunities=["Establish the initial setting"],
            unresolved_threads=[],
            risk_flags=[],
            writer_constraints=["Stay in character"],
            active_character_refs=[],
        )
        return plan, {}, {}


class _FakeWriterAdapter:
    def write(self, brief: FinalTurnBrief, snapshot: RoundSnapshot) -> WriterDraft:
        text = (
            f"[First Turn Response] "
            f"The scene begins. {brief.turn_goal}. "
            f"Player said: '{snapshot.player_input}'. "
            f"The narrative unfolds with careful attention to {brief.scene_focus}."
        )
        text += " " + "The atmosphere is rich with detail and the characters respond naturally." * 3
        return WriterDraft(
            draft_id="fake_draft_001",
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
            proposal_id="fake_proposal_001",
            patch_ops=[],
            reasoning="First turn: no state changes needed",
        )


class AWPV2PersistentFirstTurn:
    """Execute Turn 1 using RuntimeStoreFactory + SQLite.

    All L0 data loaded from SQLite (via bootstrap).
    RoundSnapshotBuilder is the canonical context entry point.
    State/Turn/Memory committed to SQLite.
    No dbPath input. Profile + namespace resolved from env.
    Idempotent replay: DuplicateTurnError → replayed receipt.
    Model profiles: director_profile_id / writer_profile_id replace free strings.
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
        "receipt", "first_turn_context", "diagnostics",
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
            request_id = f"ftr_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
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
                diagnostics_id=_id("ftd", request_id),
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
                diagnostics_id=_id("ftd", request_id),
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
            if existing_record.session_id != session_id:
                diag = FirstTurnDiagnostics(
                    diagnostics_id=_id("ftd", request_id),
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

            binding = registry.card_session_binding_store.load(session_id)
            cs = registry.card_state_store.load(
                binding.logical_card_id if binding else "", session_id
            )

            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ftd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id,
                outcome="success",
                steps_completed=["idempotent_replay"],
                agent_dispositions={"replay": "replayed"},
                turn_record_commit_status="replayed",
                card_state_commit_status="replayed",
            )

            replayed_receipt = FirstTurnReceipt(
                receipt_id=_id("ftr_replay", request_id),
                request_id=request_id,
                workflow_run_id=workflow_run_id,
                trace_id=existing_record.trace_id,
                turn_id=existing_record.turn_id,
                attempt_id="",
                session_id=session_id,
                logical_card_id=binding.logical_card_id if binding else "",
                card_version=binding.card_version if binding else 0,
                source_hash=binding.source_hash if binding else "",
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

            first_turn_ctx = {
                "turn_id": existing_record.turn_id,
                "turn_index": existing_record.turn_index,
                "turn_kind": "first",
                "session_id": session_id,
                "logical_card_id": binding.logical_card_id if binding else "",
                "idempotency_status": "replayed",
                "created_at": now,
            }

            return (
                replayed_receipt.to_dict(),
                first_turn_ctx,
                diag.to_dict(),
                cs.to_dict() if cs else {},
                existing_record.to_dict(),
                {},
            )

        diag = FirstTurnDiagnostics(
            diagnostics_id=_id("ftd", request_id),
            request_id=request_id,
            trace_id=trace_id,
            session_id=session_id,
        )
        t_start = time.time()

        # ── Load L0 from SQLite ──────────────────────────────────────────
        step_start = time.time()
        binding = registry.card_session_binding_store.load(session_id)
        if not binding:
            diag.steps_failed.append("load_binding")
            diag.outcome = "failure"
            diag.failure_message = f"No CardSessionBinding for session {session_id}"
            return ({}, {}, diag.to_dict(), {}, {}, {})

        if binding.status != "ready":
            diag.steps_failed.append("verify_session")
            diag.outcome = "failure"
            diag.failure_message = f"Session status is '{binding.status}', expected 'ready'"
            return ({}, {}, diag.to_dict(), {}, {}, {})

        opening = registry.opening_record_store.get_by_session(session_id)
        if not opening:
            diag.steps_failed.append("load_opening")
            diag.outcome = "failure"
            diag.failure_message = f"No OpeningRecord for session {session_id}"
            return ({}, {}, diag.to_dict(), {}, {}, {})

        wb_binding = registry.worldbook_binding_store.get_by_session(session_id)
        if not wb_binding:
            diag.steps_failed.append("load_worldbook")
            diag.outcome = "failure"
            diag.failure_message = f"No WorldbookBinding for session {session_id}"
            return ({}, {}, diag.to_dict(), {}, {}, {})

        diag.step_timings_ms["load_l0"] = _ms_since(step_start)
        diag.steps_completed.append("load_l0")

        # ── Build RoundSnapshot via canonical builder ────────────────────
        step_start = time.time()
        snapshot_builder = RoundSnapshotBuilder(
            card_state_store=registry.card_state_store,
            turn_record_store=registry.turn_record_store,
            active_memory_store=registry.active_memory_store,
            rag_memory_store=registry.rag_memory_store,
        )
        # First turn: L1=[], L2=[], L3=[] (no history yet)
        snapshot = snapshot_builder.build(
            card_id=binding.logical_card_id,
            session_id=session_id,
            player_input=player_input,
        )
        registry.round_snapshot_store.save(snapshot)
        diag.step_timings_ms["build_snapshot"] = _ms_since(step_start)
        diag.steps_completed.append("build_snapshot")

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
        diag.agent_dispositions = {
            "history-recall": "not_required",
            "opportunity": "not_required",
            "world-life": "not_required",
            "emotion-relationship": "not_required",
            "continuity": "not_required",
        }
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
                receipt_id=_id("ftr", request_id),
                request_id=request_id, workflow_run_id=workflow_run_id,
                trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
                session_id=session_id,
                logical_card_id=binding.logical_card_id,
                card_version=binding.card_version,
                source_hash=binding.source_hash,
                quality_verdict="reject", idempotency_status="new",
                created_at=now,
            )
            return (receipt.to_dict(), {}, diag.to_dict(), {}, {}, {})

        diag.steps_completed.append("quality_gate")

        # ── CardState Commit ────────────────────────────────────────────
        step_start = time.time()
        cs = registry.card_state_store.load(binding.logical_card_id, session_id)
        if not cs:
            cs = registry.card_state_store.initialize(binding.logical_card_id, session_id)

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
                    replayed_receipt = FirstTurnReceipt(
                        receipt_id=_id("ftr_replay", request_id),
                        request_id=request_id,
                        workflow_run_id=workflow_run_id,
                        trace_id=existing.trace_id,
                        turn_id=existing.turn_id,
                        attempt_id="",
                        session_id=session_id,
                        logical_card_id=binding.logical_card_id,
                        card_version=binding.card_version,
                        source_hash=binding.source_hash,
                        quality_verdict="accept",
                        base_card_state_revision=existing.base_card_state_revision,
                        result_card_state_revision=existing.result_card_state_revision,
                        card_state_commit_status="accepted",
                        turn_record_id=existing.turn_id,
                        turn_index=existing.turn_index,
                        turn_record_commit_status="committed",
                        memory_curation_status="noop",
                        idempotency_status="replayed",
                        created_at=now,
                    )
                    diag.turn_record_commit_status = "replayed"
                    diag.card_state_commit_status = "replayed"
                    diag.outcome = "success"
                    diag.steps_completed.append("idempotent_replay")
                    diag.step_timings_ms["total"] = _ms_since(t_start)

                    first_turn_ctx = {
                        "turn_id": existing.turn_id,
                        "turn_index": existing.turn_index,
                        "turn_kind": "first",
                        "session_id": session_id,
                        "logical_card_id": binding.logical_card_id,
                        "idempotency_status": "replayed",
                        "created_at": now,
                    }

                    return (
                        replayed_receipt.to_dict(),
                        first_turn_ctx,
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

        # Try test fixture memory curator (only in test profile)
        try:
            from ..testing.fakes.test_memory_curator_fixture import compile_test_memory_plan
            plan = compile_test_memory_plan(turn_record, snapshot, quality_decision)
            if plan and (plan.new_active_entries or plan.new_rag_entries):
                # Commit active memories
                if plan.new_active_entries:
                    active_runtime = ActiveMemoryCommitRuntime(registry.active_memory_store)
                    from ..contracts.memory_commit_plan import MemoryCommitRequest
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

                # Commit RAG memories
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
            diag.memory_curation_reason = "test_fixture_not_available"

        diag.memory_curation_status = memory_status
        diag.step_timings_ms["memory_curation"] = _ms_since(step_start)
        diag.steps_completed.append("memory_curation")

        # ── Build receipt ───────────────────────────────────────────────
        diag.outcome = "success"
        diag.step_timings_ms["total"] = _ms_since(t_start)

        receipt = FirstTurnReceipt(
            receipt_id=_id("ftr", request_id),
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
            active_memory_write_count=active_write_count,
            rag_memory_write_count=rag_write_count,
            idempotency_status="fresh",
            created_at=now,
        )

        first_turn_ctx = {
            "turn_id": turn_id,
            "turn_index": next_turn_index,
            "turn_kind": "first",
            "session_id": session_id,
            "logical_card_id": binding.logical_card_id,
            "recent_accepted_turn_count": 0,
            "active_memory_count": active_write_count,
            "rag_recall_count": rag_write_count,
            "base_card_state_revision": base_revision,
            "result_card_state_revision": result_revision,
            "opening_context": {
                "opening_record_id": opening.opening_record_id,
                "greeting_id": opening.greeting_id,
                "safe_display_content": opening.safe_display_content,
            },
            "workflow_run_id": workflow_run_id,
            "trace_id": trace_id,
            "idempotency_status": "fresh",
            "created_at": now,
        }

        return (
            receipt.to_dict(),
            first_turn_ctx,
            diag.to_dict(),
            new_state.to_dict(),
            turn_record.to_dict(),
            snapshot.to_dict(),
        )


NODE_CLASS_MAPPINGS = {
    "AWPV2PersistentFirstTurn": AWPV2PersistentFirstTurn,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2PersistentFirstTurn": "AWP V2 Persistent First Turn",
}

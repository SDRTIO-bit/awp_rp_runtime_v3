"""AWPV2PersistentContinuationTurn — continuation turn using persistent stores.

Replaces AWPV2ContinuationTurnExecution for the canonical path.
Reads all history from SQLite via SessionRuntimeLoad + RoundSnapshotBuilder.
No JSON injection of previous_turn_records, active_memories, or rag_recall.

INPUT_TYPES only accepts sessionId + playerInput + turn metadata.
All history is restored from the persistent store.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.card_state import CardState
from ..contracts.turn_record import TurnRecord
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.director_plan import DirectorPlan
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.writer_draft import WriterDraft
from ..contracts.state_update_proposal import StateUpdateProposal
from ..contracts.card_state_patch import CardStatePatch, CardStatePatchOperation, PatchOpType
from ..contracts.card_state_commit import CardStateCommitRequest, CardStateCommitStatus
from ..contracts.first_turn_receipt import FirstTurnReceipt
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics

from ..runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from ..runtime.session_runtime_load import SessionRuntimeLoad

from .session_runtime_load_node import _get_registry, _resolve_db_path


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
            writer_model="fake_writer_v1",
            prompt_tokens=0,
            completion_tokens=0,
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


class AWPV2PersistentContinuationTurn:
    """Execute a continuation turn using persistent SQLite stores.

    Key differences from AWPV2ContinuationTurnExecution:
    - NO previous_turn_records input
    - NO active_memories input
    - NO rag_recall input
    - NO card_state input (loaded from store)
    - Uses SessionRuntimeLoad to restore all state from SQLite
    - Uses RoundSnapshotBuilder for canonical L1/L2/L3 assembly

    This is the canonical continuation path for production use.
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
                "director_model": ("STRING", {"default": ""}),
                "writer_model": ("STRING", {"default": ""}),
                "db_path": ("STRING", {"default": ""}),
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
        director_model: str = "",
        writer_model: str = "",
        db_path: str = "",
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

        # ── Load from persistent stores ─────────────────────────────────
        resolved_db_path = db_path if db_path else _resolve_db_path()
        registry = _get_registry(resolved_db_path)

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

        # Extract loaded data
        snapshot = bundle.round_snapshot
        cs = bundle.card_state
        binding = bundle.card_session_binding
        opening = bundle.opening_record

        diag.step_timings_ms["session_load"] = _ms_since(t_start)
        diag.steps_completed.append("session_load")

        # Record L1/L2/L3 diagnostics
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
                request_id=request_id,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
                session_id=session_id,
                logical_card_id=binding.logical_card_id,
                card_version=binding.card_version,
                source_hash=binding.source_hash,
                quality_verdict="reject",
                idempotency_status="new",
                created_at=now,
            )
            return (receipt.to_dict(), {}, diag.to_dict(), cs.to_dict(), {}, {})

        diag.steps_completed.append("quality_gate")

        # ── State Commit ────────────────────────────────────────────────
        step_start = time.time()
        state_proposal = _FakeStateProposalAdapter().propose(candidate_text, snapshot)

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
            card_id=cs.card_id,
            session_id=cs.session_id,
            revision=cs.revision + 1,
            variables=dict(cs.variables),
            event_flags=dict(cs.event_flags),
            scene_state=cs.scene_state,
            created_at=cs.created_at,
            updated_at=now,
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
            turn_id=turn_id,
            trace_id=trace_id,
            session_id=session_id,
            card_id=binding.logical_card_id,
            turn_index=next_turn_index,
            player_input=player_input,
            writer_output=candidate_text,
            mode="normal",
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
            diag.turn_record_commit_status = "failed"
            diag.steps_failed.append("turn_commit")
            diag.outcome = "failure"
            diag.failure_message = f"TurnRecord commit failed: {e}"
            return ({}, {}, diag.to_dict(), cs.to_dict(), {}, {})

        diag.step_timings_ms["turn_commit"] = _ms_since(step_start)
        diag.steps_completed.append("turn_commit")

        # ── Memory (noop for now) ───────────────────────────────────────
        diag.memory_curation_status = "noop"
        diag.memory_curation_reason = "persistent_turn_no_adapter"
        diag.steps_completed.append("memory_curation")

        # ── Build receipt ───────────────────────────────────────────────
        diag.outcome = "success"
        diag.step_timings_ms["total"] = _ms_since(t_start)

        receipt = FirstTurnReceipt(
            receipt_id=_id("ctr", request_id),
            request_id=request_id,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
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
            memory_curation_status="noop",
            idempotency_status="new",
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
            "db_path": resolved_db_path,
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

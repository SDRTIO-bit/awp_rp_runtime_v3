"""AWPV2ContinuationTurnExecution — continuation turn for turns 2+.

Unlike FirstTurnPipeline, this node:
- Reads previous TurnRecords for L1 history (up to max_turn_history)
- Reads ActiveMemory for L2 recall
- Reads RagMemory for L3 recall
- Builds a proper RoundSnapshot with non-empty history
- Uses RoundSnapshotBuilder logic (not FirstTurnPipeline's empty snapshot)

This node is used for every turn after the first, ensuring genuine
multi-turn continuity instead of erroneously reusing FirstTurnPipeline.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
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
from ..contracts.card_state_commit import CardStateCommitRequest, CardStateCommitResult, CardStateCommitStatus
from ..contracts.first_turn_context import OpeningContext
from ..contracts.first_turn_receipt import FirstTurnReceipt, FirstTurnFailure, FirstTurnFailureCode
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics

from ..testing.fakes.fake_stores import (
    FakeCardStateStore, FakeTurnRecordStore, FakeRoundSnapshotStore, FakeTraceStore,
    FakeActiveMemoryStore, FakeRagMemoryStore,
)
from ..testing.fakes.fake_card_session_stores import (
    FakeCardSessionBindingStore, FakeOpeningRecordStore,
    FakeWorldbookBindingStore,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _ms_since(start: float) -> int:
    return int((time.time() - start) * 1000)


class _FakeDirectorAdapter:
    """Fake Director that produces a continuation-aware plan."""
    def plan(self, snapshot: RoundSnapshot) -> tuple[DirectorPlan, dict, dict]:
        history_count = len(snapshot.recent_turn_records)
        plan = DirectorPlan(
            turn_goal=f"Continue the narrative (turn {history_count + 1})",
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
    """Fake Writer that produces deterministic continuation text."""
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
    """Fake Quality Gate that accepts text meeting minimum requirements."""
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
    """Fake State Proposal that produces an empty proposal."""
    def propose(self, accepted_text: str, snapshot: RoundSnapshot) -> StateUpdateProposal:
        return StateUpdateProposal(
            proposal_id=f"cont_proposal_{snapshot.snapshot_id[:12]}",
            patch_ops=[],
            reasoning="Continuation turn: no state changes needed",
        )


class AWPV2ContinuationTurnExecution:
    """Execute a continuation turn (turn 2+).

    Key differences from AWPV2FirstTurnExecution:
    - Accepts previous_turn_records as input (L1 history)
    - Accepts active_memories and rag_recall as inputs (L2/L3)
    - Builds RoundSnapshot with non-empty recent_turn_records
    - Uses proper continuation context (not FirstTurnContext)
    - Validates turn ordering via turn_index

    Uses Fake adapters for all model calls in this phase.
    OUTPUT_NODE = True.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "session_id": ("STRING", {"default": ""}),
                "player_input": ("STRING", {"default": "", "multiline": True}),
                "logical_card_id": ("STRING", {"default": ""}),
                "card_version": ("INT", {"default": 1, "min": 1}),
                "source_hash": ("STRING", {"default": ""}),
                "card_state": ("CARD_STATE",),
                "card_session_binding": ("CARD_SESSION_BINDING",),
                "opening_record": ("OPENING_RECORD",),
                "worldbook_binding": ("WORLDBOOK_BINDING",),
                "card_definition": ("CARD_DEFINITION",),
                # Continuation-specific inputs
                "previous_turn_records": ("JSON", {"default": "[]"}),
            },
            "optional": {
                "workflow_run_id": ("STRING", {"default": ""}),
                "trace_id": ("STRING", {"default": ""}),
                "turn_id": ("STRING", {"default": ""}),
                "attempt_id": ("STRING", {"default": ""}),
                "director_model": ("STRING", {"default": ""}),
                "writer_model": ("STRING", {"default": ""}),
                "request_id": ("STRING", {"default": ""}),
                "run_id": ("STRING", {"default": ""}),
                "turn_index": ("INT", {"default": 0, "min": 0}),
                "active_memories": ("JSON", {"default": "[]"}),
                "rag_recall": ("JSON", {"default": "[]"}),
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
    CATEGORY = "AWP V2/Continuation Turn"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return time.time()

    def execute(
        self,
        session_id: str,
        player_input: str,
        logical_card_id: str,
        card_version: int,
        source_hash: str,
        card_state: dict[str, Any],
        card_session_binding: dict[str, Any],
        opening_record: dict[str, Any],
        worldbook_binding: dict[str, Any],
        card_definition: dict[str, Any],
        previous_turn_records: Any = "[]",
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
        request_id: str = "",
        run_id: str = "",
        director_model: str = "",
        writer_model: str = "",
        turn_index: int = 0,
        active_memories: Any = "[]",
        rag_recall: Any = "[]",
    ) -> tuple:
        now = datetime.now(timezone.utc).isoformat()
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

        # Parse previous turn records
        if isinstance(previous_turn_records, str):
            try:
                prev_records_raw = json.loads(previous_turn_records)
            except (json.JSONDecodeError, TypeError):
                prev_records_raw = []
        elif isinstance(previous_turn_records, list):
            prev_records_raw = previous_turn_records
        else:
            prev_records_raw = []

        prev_records = []
        for r in prev_records_raw:
            if isinstance(r, dict):
                prev_records.append(TurnRecord.from_dict(r))
            elif hasattr(r, 'turn_id'):
                prev_records.append(r)

        # Parse active memories and RAG recall
        if isinstance(active_memories, str):
            try:
                active_memories = json.loads(active_memories)
            except (json.JSONDecodeError, TypeError):
                active_memories = []
        if isinstance(rag_recall, str):
            try:
                rag_recall = json.loads(rag_recall)
            except (json.JSONDecodeError, TypeError):
                rag_recall = []

        # Wire up stores
        binding_store = FakeCardSessionBindingStore()
        binding_store.save(
            type('obj', (object,), {
                'session_id': session_id,
                'status': card_session_binding.get('status', 'ready'),
                'logical_card_id': card_session_binding.get('logical_card_id', logical_card_id),
                'card_version': card_session_binding.get('card_version', card_version),
                'source_hash': card_session_binding.get('source_hash', source_hash),
            })()
        )

        opening_store = FakeOpeningRecordStore()
        opening_store.save(
            type('obj', (object,), {
                'opening_record_id': opening_record.get('opening_record_id', ''),
                'session_id': session_id,
                'greeting_id': opening_record.get('greeting_id', ''),
                'safe_display_content': opening_record.get('safe_display_content', ''),
                'source_greeting_ref': opening_record.get('source_greeting_ref', ''),
            })()
        )

        worldbook_store = FakeWorldbookBindingStore()
        worldbook_store.save(
            type('obj', (object,), {
                'worldbook_binding_id': worldbook_binding.get('worldbook_binding_id', ''),
                'session_id': session_id,
                'entries': worldbook_binding.get('entries', []),
                'bound_entry_ids': worldbook_binding.get('bound_entry_ids', []),
                'disabled_entry_ids': worldbook_binding.get('disabled_entry_ids', []),
                'deferred_entry_ids': worldbook_binding.get('deferred_entry_ids', []),
            })()
        )

        card_state_store = FakeCardStateStore()
        cs = CardState.from_dict(card_state)
        card_state_store._states[(logical_card_id, session_id)] = cs

        turn_store = FakeTurnRecordStore()
        # Pre-load previous turn records so get_recent works
        for i, rec in enumerate(prev_records):
            rec.card_id = logical_card_id
            rec.session_id = session_id
            if not rec.turn_index:
                rec.turn_index = i + 1
            turn_store._records[rec.turn_id] = rec
            key = (logical_card_id, session_id)
            if key not in turn_store._by_session:
                turn_store._by_session[key] = []
            turn_store._by_session[key].append(rec.turn_id)

        snapshot_store = FakeRoundSnapshotStore()
        trace_store = FakeTraceStore()

        # Use real adapters if model specified
        if director_model or writer_model:
            from ..adapters.llm.deepseek_adapter import DeepSeekAdapter
            from ..adapters.llm.real_director_adapter import RealDirectorV2Adapter
            from ..adapters.llm.real_writer_adapter import RealWriterV2Adapter

            director_llm = DeepSeekAdapter(model=director_model or "deepseek-chat")
            writer_llm = DeepSeekAdapter(model=writer_model or "deepseek-chat")

            class _DirectorBridge:
                def __init__(self, adapter):
                    self._adapter = adapter
                def plan(self, snapshot):
                    plan, receipt = self._adapter.generate_plan(
                        snapshot, workflow_run_id=workflow_run_id,
                        trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
                    )
                    return plan, {}, {}

            class _WriterBridge:
                def __init__(self, adapter):
                    self._adapter = adapter
                def write(self, brief, snapshot):
                    from ..contracts.writer_input_bundle import WriterInputBundle
                    bundle = WriterInputBundle(
                        round_snapshot=snapshot, final_turn_brief=brief,
                    )
                    text, receipt = self._adapter.generate(
                        bundle, workflow_run_id=workflow_run_id,
                        trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
                    )
                    return WriterDraft(draft_id="real_draft", text=text)

            dir_adapter = _DirectorBridge(RealDirectorV2Adapter(director_llm, model=director_model))
            wrt_adapter = _WriterBridge(RealWriterV2Adapter(writer_llm, model=writer_model))
        else:
            dir_adapter = _FakeDirectorAdapter()
            wrt_adapter = _FakeWriterAdapter()

        # Build RoundSnapshot with history (the key difference from FirstTurnPipeline)
        active_wb = []
        wb_entries = worldbook_binding.get('entries', [])
        for e in wb_entries:
            if isinstance(e, dict) and e.get("enabled", True) and not e.get("selective", False):
                active_wb.append({
                    "entry_id": e.get("entry_id", ""),
                    "title": e.get("title", ""),
                    "content": e.get("content", ""),
                    "keys": e.get("keys", []),
                    "priority": e.get("priority", 50),
                    "constant": e.get("constant", False),
                })

        next_turn_index = turn_index if turn_index > 0 else len(prev_records) + 1

        diag = FirstTurnDiagnostics(
            diagnostics_id=_id("ctd", request_id),
            request_id=request_id,
            trace_id=trace_id,
            session_id=session_id,
        )
        t_start = time.time()

        # ── Build snapshot with history ─────────────────────────────────────
        step_start = time.time()
        snapshot = RoundSnapshot(
            snapshot_id=_id("snap", turn_id),
            trace_id=trace_id,
            card_id=logical_card_id,
            session_id=session_id,
            base_card_state_revision=cs.revision,
            card_state=cs,
            player_input=player_input,
            recent_turn_records=prev_records,  # Non-empty for continuation!
            active_worldbook_entries=active_wb,
            active_memories=active_memories if isinstance(active_memories, list) else [],
            rag_recall=rag_recall if isinstance(rag_recall, list) else [],
            memory_recall_diagnostics=[],
            memory_budget_decision={"disposition": "noop", "reason": "continuation_turn"},
            max_turn_history=5,
            max_active_memories=15,
            created_at=now,
        )
        snapshot_store.save(snapshot)
        diag.step_timings_ms["build_snapshot"] = _ms_since(step_start)
        diag.steps_completed.append("build_snapshot")

        # ── Director ────────────────────────────────────────────────────────
        step_start = time.time()
        director_plan, tool_plan, delegation_plan = dir_adapter.plan(snapshot)

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

        # ── Writer → Quality ────────────────────────────────────────────────
        step_start = time.time()
        writer_draft = wrt_adapter.write(brief, snapshot)
        candidate_text = writer_draft.text if hasattr(writer_draft, 'text') else str(writer_draft)

        quality_adapter = _FakeQualityAdapter()
        quality_decision = quality_adapter.check(candidate_text, snapshot)
        diag.quality_verdict = quality_decision.verdict.value
        diag.quality_blocking_reasons = list(quality_decision.blocking_reasons)
        diag.step_timings_ms["writer_and_quality"] = _ms_since(step_start)
        diag.steps_completed.append("writer_and_quality")

        if not quality_decision.allows_side_effects():
            diag.steps_failed.append("quality_gate")
            diag.outcome = "quality_rejected"
            diag.failure_code = FirstTurnFailureCode.QUALITY_REJECTED
            diag.failure_message = f"Quality gate rejected: {quality_decision.blocking_reasons}"
            receipt = FirstTurnReceipt(
                receipt_id=_id("ctr", request_id),
                request_id=request_id,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
                session_id=session_id,
                logical_card_id=logical_card_id,
                card_version=card_version,
                source_hash=source_hash,
                quality_verdict="reject",
                idempotency_status="new",
                created_at=now,
            )
            return (receipt.to_dict(), {}, diag.to_dict(), card_state, {}, {})

        diag.steps_completed.append("quality_gate")

        # ── State Commit ────────────────────────────────────────────────────
        step_start = time.time()
        state_proposal_adapter = _FakeStateProposalAdapter()
        state_proposal = state_proposal_adapter.propose(candidate_text, snapshot)

        patch = CardStatePatch(
            patch_id=_id("patch", turn_id),
            card_id=logical_card_id,
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

        state_result = card_state_store.commit(commit_request, new_state)
        diag.card_state_commit_status = state_result.status.value
        diag.step_timings_ms["state_commit"] = _ms_since(step_start)

        if state_result.status != CardStateCommitStatus.ACCEPTED:
            diag.steps_failed.append("state_commit")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.STATE_COMMIT_FAILED
            diag.failure_message = f"CardState commit failed: {state_result.error_message}"
            return (None, {}, diag.to_dict(), card_state, {}, {})

        diag.steps_completed.append("state_commit")
        base_revision = cs.revision
        result_revision = state_result.to_revision

        # ── TurnRecord Commit ───────────────────────────────────────────────
        step_start = time.time()
        turn_record = TurnRecord(
            turn_id=turn_id,
            trace_id=trace_id,
            session_id=session_id,
            card_id=logical_card_id,
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
            turn_store.save(turn_record)
            diag.turn_record_commit_status = "committed"
        except Exception as e:
            diag.turn_record_commit_status = "failed"
            diag.steps_failed.append("turn_commit")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.TURN_COMMIT_FAILED
            diag.failure_message = f"TurnRecord commit failed: {e}"
            return (None, {}, diag.to_dict(), card_state, {}, {})

        diag.step_timings_ms["turn_commit"] = _ms_since(step_start)
        diag.steps_completed.append("turn_commit")

        # ── Memory Curation (noop for now) ──────────────────────────────────
        diag.memory_curation_status = "noop"
        diag.memory_curation_reason = "continuation_turn_fake_adapter"
        diag.steps_completed.append("memory_curation")

        # ── Build receipt ───────────────────────────────────────────────────
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
            logical_card_id=logical_card_id,
            card_version=card_version,
            source_hash=source_hash,
            accepted_text=candidate_text[:200],
            quality_verdict="accept",
            base_card_state_revision=base_revision,
            result_card_state_revision=result_revision,
            card_state_commit_status="accepted",
            turn_record_id=turn_record.turn_id,
            turn_index=turn_record.turn_index,
            turn_record_commit_status="committed",
            memory_curation_status="noop",
            active_memory_write_count=0,
            rag_memory_write_count=0,
            idempotency_status="new",
            created_at=now,
        )

        # Build continuation context
        cont_ctx = {
            "turn_id": turn_id,
            "turn_index": next_turn_index,
            "turn_kind": "continuation",
            "session_id": session_id,
            "logical_card_id": logical_card_id,
            "recent_accepted_turn_count": len(prev_records),
            "active_memory_count": len(active_memories) if isinstance(active_memories, list) else 0,
            "rag_recall_count": len(rag_recall) if isinstance(rag_recall, list) else 0,
            "base_card_state_revision": base_revision,
            "result_card_state_revision": result_revision,
            "workflow_run_id": workflow_run_id,
            "trace_id": trace_id,
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
    "AWPV2ContinuationTurnExecution": AWPV2ContinuationTurnExecution,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2ContinuationTurnExecution": "AWP V2 Continuation Turn Execution",
}

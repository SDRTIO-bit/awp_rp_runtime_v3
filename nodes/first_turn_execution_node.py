"""AWPV2FirstTurnExecution -- combined node for full first turn execution.

Similar to AWPV2CardImportAndBootstrap, this node orchestrates the complete
first formal RP turn pipeline in a single execution.
"""

from __future__ import annotations

import json
import time
from typing import Any

from ..runtime.first_turn_pipeline import FirstTurnPipeline
from ..contracts.first_turn_request import FirstTurnRequest
from ..contracts.first_turn_context import OpeningContext, SessionBoundWorldbookRetrievalResult
from ..contracts.first_turn_receipt import FirstTurnReceipt, FirstTurnFailure, FirstTurnFailureCode
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.card_state import CardState
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.director_plan import DirectorPlan
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.writer_draft import WriterDraft
from ..contracts.state_update_proposal import StateUpdateProposal

from ..testing.fakes.fake_card_session_stores import (
    FakeCardSessionBindingStore, FakeOpeningRecordStore,
    FakeWorldbookBindingStore, FakeBootstrapReceiptStore,
)
from ..testing.fakes.fake_stores import (
    FakeCardStateStore, FakeTurnRecordStore, FakeRoundSnapshotStore, FakeTraceStore,
)


class _FakeDirectorAdapter:
    """Fake Director that produces a minimal plan."""
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
    """Fake Writer that produces deterministic candidate text."""
    def write(self, brief: FinalTurnBrief, snapshot: RoundSnapshot) -> WriterDraft:
        # Generate deterministic text based on the opening context
        text = (
            f"[First Turn Response] "
            f"The scene begins. {brief.turn_goal}. "
            f"Player said: '{snapshot.player_input}'. "
            f"The narrative unfolds with careful attention to {brief.scene_focus}."
        )
        # Ensure minimum length for quality gate
        text += " " + "The atmosphere is rich with detail and the characters respond naturally." * 3
        return WriterDraft(
            draft_id="fake_draft_001",
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
            proposal_id="fake_proposal_001",
            patch_ops=[],
            reasoning="First turn: no state changes needed",
        )


class AWPV2FirstTurnExecution:
    """Execute the complete first formal RP turn pipeline.

    End-to-end orchestration: validate → context → director → writer
    → quality → state commit → turn commit → memory → receipt.

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
            },
        }

    RETURN_TYPES = (
        "FIRST_TURN_RECEIPT", "FIRST_TURN_CONTEXT", "FIRST_TURN_DIAGNOSTICS",
        "CARD_STATE", "TURN_RECORD", "ROUND_SNAPSHOT",
    )
    RETURN_NAMES = (
        "first_turn_receipt", "first_turn_context", "diagnostics",
        "card_state", "turn_record", "round_snapshot",
    )
    FUNCTION = "execute"
    CATEGORY = "AWP V2/First Turn"
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
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
        request_id: str = "",
        run_id: str = "",
        director_model: str = "",
        writer_model: str = "",
    ) -> tuple:
        import hashlib
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
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

        # Build FirstTurnRequest
        request = FirstTurnRequest(
            request_id=request_id,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
            session_id=session_id,
            player_input=player_input,
            expected_logical_card_id=logical_card_id,
            expected_card_version=card_version,
            expected_source_hash=source_hash,
            created_at=now,
        )

        # Wire up fake stores with pre-loaded data
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
        # Pre-load the card state
        cs = CardState.from_dict(card_state)
        card_state_store._states[(logical_card_id, session_id)] = cs

        turn_store = FakeTurnRecordStore()
        snapshot_store = FakeRoundSnapshotStore()
        trace_store = FakeTraceStore()

        # Create adapters -- use real if model specified, fake otherwise
        if director_model or writer_model:
            from ..adapters.llm.deepseek_adapter import DeepSeekAdapter
            from ..adapters.llm.real_director_adapter import RealDirectorV2Adapter
            from ..adapters.llm.real_writer_adapter import RealWriterV2Adapter

            # Create separate adapters for director and writer with different models
            director_llm = DeepSeekAdapter(model=director_model or "deepseek-chat")
            writer_llm = DeepSeekAdapter(model=writer_model or "deepseek-chat")

            class _DirectorBridge:
                """Bridge RealDirectorV2Adapter to FirstTurnPipeline protocol."""
                def __init__(self, adapter):
                    self._adapter = adapter
                def plan(self, snapshot):
                    plan, receipt = self._adapter.generate_plan(
                        snapshot, workflow_run_id=workflow_run_id,
                        trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
                    )
                    return plan, {}, {}

            class _WriterBridge:
                """Bridge RealWriterV2Adapter to FirstTurnPipeline protocol."""
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
                    from ..contracts.writer_draft import WriterDraft
                    return WriterDraft(draft_id="real_draft", text=text)

            dir_adapter = _DirectorBridge(RealDirectorV2Adapter(director_llm, model=director_model))
            wrt_adapter = _WriterBridge(RealWriterV2Adapter(writer_llm, model=writer_model))
        else:
            dir_adapter = _FakeDirectorAdapter()
            wrt_adapter = _FakeWriterAdapter()

        # Create pipeline with adapters
        pipeline = FirstTurnPipeline(
            card_state_store=card_state_store,
            turn_record_store=turn_store,
            round_snapshot_store=snapshot_store,
            trace_store=trace_store,
            binding_store=binding_store,
            opening_store=opening_store,
            worldbook_store=worldbook_store,
            director_adapter=dir_adapter,
            writer_adapter=wrt_adapter,
            quality_adapter=_FakeQualityAdapter(),
            state_proposal_adapter=_FakeStateProposalAdapter(),
        )

        receipt, failure, diag = pipeline.execute(request)

        # Build outputs
        receipt_dict = receipt.to_dict() if receipt else {}
        diag_dict = diag.to_dict()

        # Extract accepted text and receipt JSON
        accepted_text = receipt_dict.get("accepted_text", "")
        receipt_json_str = json.dumps(receipt_dict, ensure_ascii=False) if receipt_dict else "{}"

        # Write output to file for runner extraction
        try:
            from pathlib import Path
            output_dir = Path("artifacts/real-provider-outputs")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"turn_{turn_id[:16]}.json"
            output_file.write_text(json.dumps({
                "turn_id": turn_id,
                "accepted_text": accepted_text,
                "quality_verdict": receipt_dict.get("quality_verdict", ""),
                "receipt": receipt_dict,
                "diagnostics": diag_dict,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # Never fail the node due to output writing

        # Load committed state and turn record
        committed_state = card_state_store.load(logical_card_id, session_id)
        committed_turn = turn_store.load(turn_id)

        # Build FirstTurnContext for output
        from ..contracts.first_turn_context import FirstTurnContext
        ctx = FirstTurnContext(
            context_id=f"ftc_{turn_id[:16]}",
            trace_id=trace_id,
            session_id=session_id,
            logical_card_id=logical_card_id,
            card_version=card_version,
            source_hash=source_hash,
            card_session_binding_id=session_id,
            card_state_revision=committed_state.revision if committed_state else 0,
            card_state=committed_state.to_dict() if committed_state else {},
            opening_context=OpeningContext(
                opening_record_id=opening_record.get('opening_record_id', ''),
                greeting_id=opening_record.get('greeting_id', ''),
                safe_display_content=opening_record.get('safe_display_content', ''),
                source_greeting_ref=opening_record.get('source_greeting_ref', ''),
            ).to_dict(),
            player_input=player_input,
            worldbook_retrieval={},
            round_snapshot_id="",
            round_snapshot={},
            is_first_turn=True,
            recent_accepted_turn_count=0,
            active_memory_count=0,
            rag_recall_count=0,
            workflow_run_id=workflow_run_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
            created_at=now,
        )

        return (
            receipt_dict,
            ctx.to_dict(),
            diag_dict,
            committed_state.to_dict() if committed_state else card_state,
            committed_turn.to_dict() if committed_turn else {},
            {},  # round_snapshot (saved in store)
        )


NODE_CLASS_MAPPINGS = {
    "AWPV2FirstTurnExecution": AWPV2FirstTurnExecution,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2FirstTurnExecution": "AWP V2 首回合执行",
}

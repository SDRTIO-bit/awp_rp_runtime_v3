"""AWPV2PersistentContinuationTurn — Turn 2+ using RuntimeStoreFactory + SQLite.

All history restored from SQLite via SessionRuntimeLoad + RoundSnapshotBuilder.
No dbPath input. No JSON injection. No Fake stores for state/turn/memory.

Director/Writer adapters are resolved from model profiles (fake or real
DeepSeek). D6 runs the deterministic curation path on every accepted turn —
no silent noop in production/real profiles.

Idempotent replay: same sessionId + turnId + requestId returns the existing
completed receipt without re-calling Provider or re-writing state.
"""

from __future__ import annotations

import time
from typing import Any

from ..contracts.card_state import CardState
from ..contracts.first_turn_receipt import FirstTurnReceipt
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics

from ..runtime.runtime_store_factory import RuntimeStoreFactory
from ..runtime.session_runtime_load import SessionRuntimeLoad
from ..runtime.persistent_turn_engine import PersistentTurnEngine, _id, _now
from ..adapters.llm.model_profile_registry import ModelProfileRegistry


def _build_replayed_receipt(
    existing_record,
    request_id: str,
    workflow_run_id: str,
    session_id: str,
    binding: Any,
    now: str,
) -> FirstTurnReceipt:
    """Build a replayed receipt from an existing TurnRecord.

    Returns a safe preview of the original accepted text so an upper layer
    can restore the reply (the full text remains in the TurnRecord).
    """
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
        accepted_text=existing_record.writer_output[:200] if existing_record.writer_output else "",
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
    - D6 runs the deterministic MemoryCurationRuntime on every accepted turn
    - RoundSnapshotBuilder is the canonical context entry point
    - Idempotent replay: existing turn_id → replayed receipt (no provider calls)
    - Model profiles: director_profile_id / writer_profile_id (fake or real)
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
            request_id = _id("ctr", seed)
        if not workflow_run_id:
            workflow_run_id = _id("wfr", seed)
        if not trace_id:
            trace_id = _id("trc", seed)
        if not turn_id:
            turn_id = _id("turn", seed)
        if not attempt_id:
            attempt_id = _id("att", seed)

        # ── Validate model profiles ──────────────────────────────────────
        try:
            ModelProfileRegistry.resolve(director_profile_id)
        except ValueError as e:
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ctd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id, director_profile_id=director_profile_id,
                outcome="failure", failure_message=str(e),
                steps_failed=["model_profile_validation"], failure_code="UNKNOWN_PROFILE",
            )
            return ({}, {}, diag.to_dict(), {}, {}, {})

        try:
            ModelProfileRegistry.resolve(writer_profile_id)
        except ValueError as e:
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ctd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id, writer_profile_id=writer_profile_id,
                outcome="failure", failure_message=str(e),
                steps_failed=["model_profile_validation"], failure_code="UNKNOWN_PROFILE",
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
                    diagnostics_id=_id("ctd", request_id),
                    request_id=request_id, trace_id=trace_id,
                    session_id=session_id, outcome="failure",
                    failure_message=(
                        f"Turn '{turn_id}' belongs to session "
                        f"'{existing_record.session_id}', not '{session_id}'"
                    ),
                    steps_failed=["session_binding_conflict"],
                    failure_code="SESSION_BINDING_CONFLICT",
                )
                return ({}, {}, diag.to_dict(), {}, {}, {})

            binding = registry.card_session_binding_store.load(session_id)
            if not binding:
                diag = FirstTurnDiagnostics(
                    diagnostics_id=_id("ctd", request_id),
                    request_id=request_id, trace_id=trace_id,
                    session_id=session_id, outcome="failure",
                    failure_message=f"No CardSessionBinding for session {session_id}",
                    steps_failed=["session_load"], failure_code="SESSION_NOT_FOUND",
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
                session_id=session_id, outcome="success",
                steps_completed=["idempotent_replay"],
                agent_dispositions={"replay": "replayed"},
                turn_record_commit_status="replayed",
                card_state_commit_status="replayed",
                turn_record_id=existing_record.turn_id,
                trace_persisted=True,
            )

            cont_ctx = {
                "turn_id": existing_record.turn_id,
                "turn_index": existing_record.turn_index,
                "turn_kind": "continuation",
                "session_id": session_id,
                "logical_card_id": binding.logical_card_id,
                "idempotency_status": "replayed",
                "recoverable_accepted_text_ref": existing_record.turn_id,
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
            request_id=request_id, trace_id=trace_id,
            session_id=session_id,
        )

        if not bundle.is_valid:
            diag.outcome = "failure"
            diag.failure_message = "; ".join(bundle.load_errors)
            diag.steps_failed.append("session_load")
            diag.failure_code = "SESSION_LOAD_FAILED"
            return ({}, {}, diag.to_dict(), {}, {}, {})

        snapshot = bundle.round_snapshot
        cs = bundle.card_state
        binding = bundle.card_session_binding

        diag.agent_dispositions = {
            "history-recall": "loaded" if bundle.l1_turn_count > 0 else "empty",
            "active-memory": "loaded" if bundle.l2_active_memory_count > 0 else "empty",
            "rag-memory": "loaded" if bundle.l3_rag_recall_count > 0 else "empty",
        }
        diag.steps_completed.append("session_load")

        # ── Run the shared persistent turn engine ────────────────────────
        profile = factory.profile
        engine = PersistentTurnEngine(registry, profile=profile)
        return engine.execute(
            session_id=session_id,
            player_input=player_input,
            binding=binding,
            snapshot=snapshot,
            card_state=cs,
            turn_id=turn_id,
            attempt_id=attempt_id,
            request_id=request_id,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            director_profile_id=director_profile_id,
            writer_profile_id=writer_profile_id,
            turn_kind="continuation",
        )


NODE_CLASS_MAPPINGS = {
    "AWPV2PersistentContinuationTurn": AWPV2PersistentContinuationTurn,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2PersistentContinuationTurn": "AWP V2 Persistent Continuation Turn",
}

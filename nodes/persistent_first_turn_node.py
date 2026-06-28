"""AWPV2PersistentFirstTurn — Turn 1 using RuntimeStoreFactory + SQLite.

Replaces AWPV2FirstTurnExecution for the canonical persistent path.
All stores come from RuntimeStoreFactory. No Fake stores. No dbPath input.
Uses SessionRuntimeLoad + RoundSnapshotBuilder for context assembly.
Commits to SQLite: CardState, TurnRecord, D6 Memory.

The Director/Writer adapters are resolved from model profiles:
  fake-director / fake-writer → deterministic fake (offline tests).
  real profile → real DeepSeek adapter (no silent fallback to fake).

Idempotent replay: same sessionId + turnId + requestId returns the existing
completed receipt without re-calling Provider or re-writing state.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.card_state import CardState
from ..contracts.first_turn_receipt import FirstTurnReceipt
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics

from ..runtime.runtime_store_factory import RuntimeStoreFactory
from ..runtime.round_snapshot_builder import RoundSnapshotBuilder
from ..runtime.persistent_turn_engine import PersistentTurnEngine, _id, _now
from ..adapters.llm.model_profile_registry import ModelProfileRegistry


class AWPV2PersistentFirstTurn:
    """Execute Turn 1 using RuntimeStoreFactory + SQLite.

    All L0 data loaded from SQLite (via bootstrap).
    RoundSnapshotBuilder is the canonical context entry point.
    State/Turn/Memory committed to SQLite.
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
                "writer_preset_path": ("STRING", {"default": ""}),
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
        writer_preset_path: str = "",
    ) -> tuple:
        now = _now()
        seed = f"{session_id}:{now}:{run_id}"

        if not request_id:
            request_id = _id("ftr", seed)
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
                diagnostics_id=_id("ftd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id, director_profile_id=director_profile_id,
                outcome="failure", failure_message=str(e),
                steps_failed=["model_profile_validation"],
                failure_code="UNKNOWN_PROFILE",
            )
            return ({}, {}, diag.to_dict(), {}, {}, {})

        try:
            ModelProfileRegistry.resolve(writer_profile_id)
        except ValueError as e:
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ftd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id, writer_profile_id=writer_profile_id,
                outcome="failure", failure_message=str(e),
                steps_failed=["model_profile_validation"],
                failure_code="UNKNOWN_PROFILE",
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
                    failure_code="SESSION_BINDING_CONFLICT",
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
                turn_record_id=existing_record.turn_id,
                trace_persisted=True,
            )

            # Replay returns recoverable accepted text (safe preview) so an
            # upper layer can restore the original reply without leaking
            # internal chains. The full text lives in the TurnRecord.
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

            first_turn_ctx = {
                "turn_id": existing_record.turn_id,
                "turn_index": existing_record.turn_index,
                "turn_kind": "first",
                "session_id": session_id,
                "logical_card_id": binding.logical_card_id if binding else "",
                "idempotency_status": "replayed",
                "recoverable_accepted_text_ref": existing_record.turn_id,
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

        # ── Load L0 from SQLite ──────────────────────────────────────────
        binding = registry.card_session_binding_store.load(session_id)
        if not binding:
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ftd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id, outcome="failure",
                failure_message=f"No CardSessionBinding for session {session_id}",
                steps_failed=["load_binding"], failure_code="SESSION_NOT_FOUND",
            )
            return ({}, {}, diag.to_dict(), {}, {}, {})

        if binding.status != "ready":
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ftd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id, outcome="failure",
                failure_message=f"Session status is '{binding.status}', expected 'ready'",
                steps_failed=["verify_session"], failure_code="SESSION_NOT_READY",
            )
            return ({}, {}, diag.to_dict(), {}, {}, {})

        opening = registry.opening_record_store.get_by_session(session_id)
        if not opening:
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ftd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id, outcome="failure",
                failure_message=f"No OpeningRecord for session {session_id}",
                steps_failed=["load_opening"], failure_code="OPENING_RECORD_NOT_FOUND",
            )
            return ({}, {}, diag.to_dict(), {}, {}, {})

        wb_binding = registry.worldbook_binding_store.get_by_session(session_id)
        if not wb_binding:
            diag = FirstTurnDiagnostics(
                diagnostics_id=_id("ftd", request_id),
                request_id=request_id, trace_id=trace_id,
                session_id=session_id, outcome="failure",
                failure_message=f"No WorldbookBinding for session {session_id}",
                steps_failed=["load_worldbook"], failure_code="WORLDBOOK_BINDING_NOT_FOUND",
            )
            return ({}, {}, diag.to_dict(), {}, {}, {})

        # ── Build RoundSnapshot via canonical builder ────────────────────
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

        cs = registry.card_state_store.load(binding.logical_card_id, session_id)
        if not cs:
            cs = registry.card_state_store.initialize(binding.logical_card_id, session_id)

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
            turn_kind="first",
            writer_preset_path=writer_preset_path,
        )


NODE_CLASS_MAPPINGS = {
    "AWPV2PersistentFirstTurn": AWPV2PersistentFirstTurn,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2PersistentFirstTurn": "AWP V2 Persistent First Turn",
}

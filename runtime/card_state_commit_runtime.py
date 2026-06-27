"""CardStateCommitRuntime — the ONLY writer for CardState.

All state writes must go through this runtime.
Enforces:
- Gate must pass (assert_side_effects_allowed)
- traceId must match QualityDecision
- Revision checks
- Idempotency via patchId
- Full operation validation (any illegal → zero writes)
- Atomic transaction
"""

from __future__ import annotations

from ..contracts.card_state import CardState
from ..contracts.card_state_patch import CardStatePatch, PatchOpType
from ..contracts.card_state_commit import (
    CardStateCommitRequest, CardStateCommitResult, CardStateCommitStatus,
)
from ..contracts.quality_decision import (
    QualityDecision, assert_side_effects_allowed, SideEffectBlockedError,
)
from ..storage.interfaces import CardStateStore


class CardStateCommitRuntime:
    """The ONLY runtime that can write CardState."""

    def __init__(self, store: CardStateStore):
        self.store = store

    def commit(
        self,
        patch: CardStatePatch,
        quality_decision: QualityDecision,
        expected_revision: int,
    ) -> CardStateCommitResult:
        """Commit state changes.

        Gate must accept. traceId must match.
        All ops validated atomically.
        """
        # Gate check
        try:
            assert_side_effects_allowed(quality_decision)
        except SideEffectBlockedError as e:
            return CardStateCommitResult(
                status=CardStateCommitStatus.GATE_REJECTED,
                card_id=patch.card_id,
                session_id=patch.session_id,
                patch_id=patch.patch_id,
                trace_id=patch.trace_id,
                error_message=str(e),
            )

        # traceId match
        if quality_decision.trace_id and patch.trace_id:
            if quality_decision.trace_id != patch.trace_id:
                return CardStateCommitResult(
                    status=CardStateCommitStatus.TRACE_MISMATCH,
                    card_id=patch.card_id,
                    session_id=patch.session_id,
                    patch_id=patch.patch_id,
                    trace_id=patch.trace_id,
                    error_message=(
                        f"traceId mismatch: decision={quality_decision.trace_id}, "
                        f"patch={patch.trace_id}"
                    ),
                )

        # Load current state and apply operations to build new state
        current = self.store.load(patch.card_id, patch.session_id)
        if not current:
            return CardStateCommitResult(
                status=CardStateCommitStatus.INTERNAL_ERROR,
                card_id=patch.card_id,
                session_id=patch.session_id,
                patch_id=patch.patch_id,
                error_message=f"No CardState for {patch.card_id}/{patch.session_id}",
            )

        new_state = self._apply_operations(current, patch.operations)

        # Build request and delegate to store
        request = CardStateCommitRequest(
            patch=patch,
            expected_revision=expected_revision,
            quality_decision_ref=quality_decision.source_turn_id,
            trace_id=patch.trace_id,
        )

        return self.store.commit(request, new_state)

    def _apply_operations(self, state: CardState, operations: list) -> CardState:
        """Apply patch operations to produce a new CardState (deep copy)."""
        import copy
        data = state.to_dict()

        for op in operations:
            parts = op.path.split(".")
            prefix = parts[0]
            key = parts[1] if len(parts) > 1 else ""

            if op.op == PatchOpType.SET:
                if prefix == "variables":
                    data["variables"][key] = {
                        "name": key, "value": op.value,
                        "var_type": type(op.value).__name__ if op.value is not None else "string",
                        "description": "", "last_updated_turn": None,
                    }

            elif op.op == PatchOpType.REMOVE:
                if prefix == "variables" and key in data["variables"]:
                    del data["variables"][key]
                elif prefix == "event_flags" and key in data["event_flags"]:
                    del data["event_flags"][key]

            elif op.op == PatchOpType.INCREMENT:
                if prefix == "variables" and key in data["variables"]:
                    delta = op.value if op.value is not None else 1
                    data["variables"][key]["value"] = data["variables"][key].get("value", 0) + delta

            elif op.op == PatchOpType.APPEND_UNIQUE:
                if prefix == "active_stage_ids":
                    if key and key not in data["active_stage_ids"]:
                        data["active_stage_ids"].append(key)

            elif op.op == PatchOpType.SET_FLAG:
                if prefix == "event_flags":
                    data["event_flags"][key] = {
                        "event_id": key, "fired": True,
                        "fired_at_turn": None,
                        "metadata": op.value if isinstance(op.value, dict) else {},
                    }

            elif op.op == PatchOpType.ACTIVATE_STAGE:
                if prefix == "active_stage_ids" and op.value and op.value not in data["active_stage_ids"]:
                    data["active_stage_ids"].append(op.value)

            elif op.op == PatchOpType.DEACTIVATE_STAGE:
                if prefix == "active_stage_ids" and op.value in data["active_stage_ids"]:
                    data["active_stage_ids"].remove(op.value)

            elif op.op == PatchOpType.SET_SCENE_FIELD:
                if prefix == "scene_state" and key:
                    data["scene_state"][key] = op.value

        return CardState.from_dict(data)

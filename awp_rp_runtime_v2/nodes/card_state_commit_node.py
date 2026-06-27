"""AWPV2CardStateCommit — the ONLY node that writes CardState.

Input: state_update_proposal (JSON patch), quality_decision, expected_revision, patch_id, trace_id
Output: commit_result (JSON with status)
"""

from __future__ import annotations

from typing import Any


class AWPV2CardStateCommit:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "state_update_proposal": ("STATE_UPDATE_PROPOSAL",),
                "quality_decision": ("QUALITY_DECISION",),
                "expected_revision": ("INT",),
                "patch_id": ("STRING",),
            },
            "optional": {
                "trace_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("CARD_STATE_COMMIT_RESULT", "CARD_STATE")
    RETURN_NAMES = ("commit_result", "new_card_state")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        state_update_proposal: dict[str, Any],
        quality_decision: dict[str, Any],
        expected_revision: int,
        patch_id: str,
        trace_id: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from ..contracts.card_state_patch import CardStatePatch, CardStatePatchOperation, PatchOpType
        from ..contracts.quality_decision import QualityDecision, assert_side_effects_allowed
        from ..contracts.state_update_proposal import StateUpdateProposal

        decision = QualityDecision.from_dict(quality_decision)

        # Gate check
        assert_side_effects_allowed(decision)

        # Convert proposal → patch
        proposal = StateUpdateProposal.from_dict(state_update_proposal)
        op_type_map = {
            "set_variable": PatchOpType.SET,
            "increment_variable": PatchOpType.INCREMENT,
            "decrement_variable": PatchOpType.INCREMENT,
            "set_event_flag": PatchOpType.SET_FLAG,
            "clear_event_flag": PatchOpType.REMOVE,
            "set_scene": PatchOpType.SET_SCENE_FIELD,
            "add_active_stage": PatchOpType.ACTIVATE_STAGE,
            "remove_active_stage": PatchOpType.DEACTIVATE_STAGE,
        }

        operations = []
        for op in proposal.operations:
            mapped = op_type_map.get(op.op.value if hasattr(op.op, 'value') else op.op)
            if mapped:
                value = op.value
                if op.op.value == "decrement_variable" and isinstance(value, (int, float)):
                    value = -value
                operations.append(CardStatePatchOperation(
                    op=mapped, path=op.path, value=value,
                    reason=getattr(op, 'reason', ''),
                ))

        patch = CardStatePatch(
            patch_id=patch_id,
            card_id=proposal.card_id,
            session_id=proposal.session_id,
            operations=operations,
            trace_id=trace_id or decision.trace_id,
        )

        # Return the patch as result (actual commit requires store)
        return (patch.to_dict(), patch.to_dict())

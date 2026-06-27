"""AWPV2EmotionRelationshipRequest — ComfyUI node for building EmotionRelationshipRequest."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..runtime.emotion_relationship_trigger_policy import EmotionRelationshipTriggerResult
from ..contracts.emotion_relationship_request import EmotionRelationshipRequest


class AWPV2EmotionRelationshipRequest:
    """Build EmotionRelationshipRequest from trigger result and snapshot."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "er_trigger_result": ("ER_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("ER_REQUEST",)
    RETURN_NAMES = ("request",)
    FUNCTION = "build"
    CATEGORY = "AWP V2/EmotionRelationship"

    def build(
        self,
        round_snapshot: RoundSnapshot,
        er_trigger_result: EmotionRelationshipTriggerResult,
    ) -> tuple:
        request = EmotionRelationshipRequest(
            request_id=f"er_req_{round_snapshot.snapshot_id[:8]}",
            trace_id=round_snapshot.trace_id,
            snapshot_id=round_snapshot.snapshot_id,
            card_id=round_snapshot.card_id,
            session_id=round_snapshot.session_id,
            focus_entities=er_trigger_result.focus_entities,
            player_intent=round_snapshot.player_input[:100],
            must_not_create_facts=True,
            must_not_modify_relationships=True,
        )
        return (request,)

"""AWPV2OpportunityRequest — ComfyUI node for building OpportunityRequest."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..runtime.opportunity_trigger_policy import OpportunityTriggerResult
from ..contracts.opportunity_request import OpportunityRequest


class AWPV2OpportunityRequest:
    """Build OpportunityRequest from trigger result and snapshot."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "trigger_result": ("OPPORTUNITY_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("OPPORTUNITY_REQUEST",)
    RETURN_NAMES = ("request",)
    FUNCTION = "build"
    CATEGORY = "AWP V2/Opportunity"

    def build(
        self,
        round_snapshot: RoundSnapshot,
        trigger_result: OpportunityTriggerResult,
    ) -> tuple:
        request = OpportunityRequest(
            request_id=f"opr_req_{round_snapshot.snapshot_id[:8]}",
            trace_id=round_snapshot.trace_id,
            snapshot_id=round_snapshot.snapshot_id,
            card_id=round_snapshot.card_id,
            session_id=round_snapshot.session_id,
            focus_entities=trigger_result.focus_entities,
            player_intent=round_snapshot.player_input[:100],
            must_not_create_facts=True,
        )
        return (request,)

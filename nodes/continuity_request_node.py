"""AWPV2ContinuityRequest — ComfyUI node for building ContinuityRequest."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..runtime.continuity_trigger_policy import ContinuityTriggerResult
from ..contracts.continuity_request import ContinuityRequest


class AWPV2ContinuityRequest:
    """Build a ContinuityRequest from trigger result and snapshot."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "trigger_result": ("CONTINUITY_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("CONTINUITY_REQUEST",)
    RETURN_NAMES = ("continuity_request",)
    FUNCTION = "build"
    CATEGORY = "AWP V2/Continuity"

    def build(
        self,
        round_snapshot: RoundSnapshot,
        trigger_result: ContinuityTriggerResult,
    ) -> tuple:
        request = ContinuityRequest(
            request_id=f"clr_req_{round_snapshot.snapshot_id}",
            trace_id=round_snapshot.trace_id,
            snapshot_id=round_snapshot.snapshot_id,
            card_id=round_snapshot.card_id,
            session_id=round_snapshot.session_id,
            focus_entities=trigger_result.focus_entities,
            focus_locations=trigger_result.focus_locations,
            focus_turns=trigger_result.focus_turns,
            max_issues=trigger_result.max_issue_count,
            required_evidence=True,
        )
        return (request,)

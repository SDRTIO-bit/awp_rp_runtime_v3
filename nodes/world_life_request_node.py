"""AWPV2WorldLifeRequest — ComfyUI node for building WorldLifeRequest."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..runtime.world_life_trigger_policy import WorldLifeTriggerResult
from ..contracts.world_life_request import WorldLifeRequest


class AWPV2WorldLifeRequest:
    """Build WorldLifeRequest from trigger result and snapshot."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "trigger_result": ("WORLD_LIFE_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("WORLD_LIFE_REQUEST",)
    RETURN_NAMES = ("request",)
    FUNCTION = "build"
    CATEGORY = "AWP V2/WorldLife"

    def build(
        self,
        round_snapshot: RoundSnapshot,
        trigger_result: WorldLifeTriggerResult,
    ) -> tuple:
        scene_location = round_snapshot.card_state.scene_state.location if round_snapshot.card_state.scene_state else ""
        request = WorldLifeRequest(
            request_id=f"wlr_req_{round_snapshot.snapshot_id[:8]}",
            trace_id=round_snapshot.trace_id,
            snapshot_id=round_snapshot.snapshot_id,
            card_id=round_snapshot.card_id,
            session_id=round_snapshot.session_id,
            focus_entities=trigger_result.focus_entities,
            focus_locations=trigger_result.focus_locations,
            focus_event_stages=trigger_result.focus_event_stages,
            current_scene_summary=f"地点: {scene_location}",
            player_intent=round_snapshot.player_input[:100],
            must_not_create_facts=True,
            must_not_advance_timeline=True,
            must_not_modify_card_state=True,
        )
        return (request,)

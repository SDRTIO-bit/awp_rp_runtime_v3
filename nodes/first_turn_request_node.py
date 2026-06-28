"""AWPV2FirstTurnRequest -- creates a FirstTurnRequest contract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.first_turn_request import FirstTurnRequest


class AWPV2FirstTurnRequest:
    """Create a FirstTurnRequest for the first formal RP turn.

    Inputs:
      session_id: Session to execute turn on
      player_input: Player's first input text
      logical_card_id: Expected card identity
      card_version: Expected card version
      source_hash: Expected source hash for integrity
    Optional:
      workflow_run_id, trace_id, turn_id, attempt_id: Identity quartet
    Outputs:
      FIRST_TURN_REQUEST
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
            },
            "optional": {
                "workflow_run_id": ("STRING", {"default": ""}),
                "trace_id": ("STRING", {"default": ""}),
                "turn_id": ("STRING", {"default": ""}),
                "attempt_id": ("STRING", {"default": ""}),
                "request_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("FIRST_TURN_REQUEST",)
    RETURN_NAMES = ("first_turn_request",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2/First Turn"
    OUTPUT_NODE = False

    def execute(
        self,
        session_id: str,
        player_input: str,
        logical_card_id: str,
        card_version: int,
        source_hash: str,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
        request_id: str = "",
    ) -> tuple[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        # Generate deterministic IDs if not provided
        import hashlib
        seed = f"{session_id}:{now}"
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
        return (request.to_dict(),)


# Node registration
NODE_CLASS_MAPPINGS = {
    "AWPV2FirstTurnRequest": AWPV2FirstTurnRequest,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2FirstTurnRequest": "AWP V2 首回合请求",
}

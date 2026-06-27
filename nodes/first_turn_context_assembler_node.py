"""AWPV2FirstTurnContextAssembler -- assembles FirstTurnContext for Director/Writer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.first_turn_context import FirstTurnContext


class AWPV2FirstTurnContextAssembler:
    """Assemble FirstTurnContext from validated session data.

    Combines:
      - Session binding identity
      - CardState revision
      - OpeningContext reference
      - Worldbook retrieval result
      - RoundSnapshot (with empty history/memory for first turn)
      - Player input

    First turn markers:
      - recentAcceptedTurns = []
      - activeMemories = []
      - ragRecall = []
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "first_turn_request": ("FIRST_TURN_REQUEST",),
                "card_session_binding": ("CARD_SESSION_BINDING",),
                "card_state": ("CARD_STATE",),
                "opening_context": ("OPENING_CONTEXT",),
                "worldbook_retrieval": ("WORLDBOOK_RETRIEVAL_RESULT",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
        }

    RETURN_TYPES = ("FIRST_TURN_CONTEXT",)
    RETURN_NAMES = ("first_turn_context",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2/First Turn"
    OUTPUT_NODE = False

    def execute(
        self,
        first_turn_request: dict[str, Any],
        card_session_binding: dict[str, Any],
        card_state: dict[str, Any],
        opening_context: dict[str, Any],
        worldbook_retrieval: dict[str, Any],
        round_snapshot: dict[str, Any],
    ) -> tuple[dict]:
        now = datetime.now(timezone.utc).isoformat()
        ctx = FirstTurnContext(
            context_id=f"ftc_{first_turn_request.get('turn_id', '')[:16]}",
            trace_id=first_turn_request.get("trace_id", ""),
            session_id=first_turn_request.get("session_id", ""),
            logical_card_id=card_session_binding.get("logical_card_id", ""),
            card_version=card_session_binding.get("card_version", 0),
            source_hash=card_session_binding.get("source_hash", ""),
            card_session_binding_id=card_session_binding.get("session_id", ""),
            card_state_revision=card_state.get("revision", 0),
            card_state=card_state,
            opening_context=opening_context,
            player_input=first_turn_request.get("player_input", ""),
            worldbook_retrieval=worldbook_retrieval,
            round_snapshot_id=round_snapshot.get("snapshot_id", ""),
            round_snapshot=round_snapshot,
            is_first_turn=True,
            recent_accepted_turn_count=0,
            active_memory_count=0,
            rag_recall_count=0,
            workflow_run_id=first_turn_request.get("workflow_run_id", ""),
            turn_id=first_turn_request.get("turn_id", ""),
            attempt_id=first_turn_request.get("attempt_id", ""),
            created_at=now,
        )
        return (ctx.to_dict(),)


NODE_CLASS_MAPPINGS = {
    "AWPV2FirstTurnContextAssembler": AWPV2FirstTurnContextAssembler,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2FirstTurnContextAssembler": "AWP V2 首回合上下文装配",
}

"""AWPV2CardStateInit — initialize or load CardState.

Output: CARD_STATE (JSON)
"""

from __future__ import annotations

from typing import Any


class AWPV2CardStateInit:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "card_id": ("STRING", {"default": ""}),
                "session_id": ("STRING", {"default": ""}),
            },
            "optional": {
                "greeting": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("CARD_STATE",)
    RETURN_NAMES = ("card_state",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(self, card_id: str, session_id: str, greeting: str = "") -> tuple[dict[str, Any]]:
        from ..contracts.card_state import CardState
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        state = CardState(
            card_id=card_id, session_id=session_id, revision=0,
            created_at=now, updated_at=now,
        )
        return (state.to_dict(),)

"""AWPV2AcceptedTurnWindow — L1 window of the last <=5 accepted turns.

Output: ACCEPTED_TURN_WINDOW (JSON), TURN_COUNT
"""

from __future__ import annotations

from typing import Any


class AWPV2AcceptedTurnWindow:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "turn_records": ("TURN_RECORDS",),
                "card_id": ("STRING",),
                "session_id": ("STRING",),
            },
            "optional": {
                "snapshot_id": ("STRING", {"default": ""}),
                "window_size": ("INT", {"default": 5, "min": 1, "max": 5}),
            },
        }

    RETURN_TYPES = ("ACCEPTED_TURN_WINDOW", "INT")
    RETURN_NAMES = ("accepted_turn_window", "turn_count")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"
    OUTPUT_SCHEMA_ID = "awp.rp.accepted-turn-window.v1"

    def execute(
        self,
        turn_records: list,
        card_id: str,
        session_id: str,
        snapshot_id: str = "",
        window_size: int = 5,
    ) -> tuple[dict[str, Any], int]:
        from ..contracts.turn_record import TurnRecord
        from ..contracts.accepted_turn_window import AcceptedTurnWindow

        turns = [TurnRecord.from_dict(t) if isinstance(t, dict) else t for t in (turn_records or [])]
        window = AcceptedTurnWindow.build(
            card_id=card_id, session_id=session_id, turns=turns,
            snapshot_id=snapshot_id, window_size=window_size,
        )
        return (window.to_dict(), len(window.turns))

"""AWPV2ContinueTurn — handle turn continuation.

Continue must be based on last accepted TurnRecord.
Player input is empty or "continue".
"""

from __future__ import annotations

from typing import Any


class AWPV2ContinueTurn:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "last_turn_record": ("TURN_RECORD",),
            },
        }

    RETURN_TYPES = ("STRING", "CARD_STATE", "BOOLEAN")
    RETURN_NAMES = ("continue_input", "card_state", "valid")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(self, last_turn_record: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
        from ..contracts.turn_record import TurnRecord

        record = TurnRecord.from_dict(last_turn_record)

        if not record.turn_id:
            return ("", {}, False)

        # Continue: use empty input, carry forward the card state reference
        return ("continue", {}, True)

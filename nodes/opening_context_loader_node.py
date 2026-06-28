"""AWPV2OpeningContextLoader -- loads OpeningContext from OpeningRecord."""

from __future__ import annotations

from typing import Any

from ..contracts.first_turn_context import OpeningContext


class AWPV2OpeningContextLoader:
    """Load OpeningContext from a bootstrapped Session's OpeningRecord.

    OpeningContext is a controlled projection of OpeningRecord.
    It is NOT a TurnRecord and must not be confused with one.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "opening_record": ("OPENING_RECORD",),
            },
        }

    RETURN_TYPES = ("OPENING_CONTEXT",)
    RETURN_NAMES = ("opening_context",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2/First Turn"
    OUTPUT_NODE = False

    def execute(self, opening_record: dict[str, Any]) -> tuple[dict]:
        ctx = OpeningContext(
            opening_record_id=opening_record.get("opening_record_id", ""),
            greeting_id=opening_record.get("greeting_id", ""),
            safe_display_content=opening_record.get("safe_display_content", ""),
            source_greeting_ref=opening_record.get("source_greeting_ref", ""),
        )
        return (ctx.to_dict(),)


NODE_CLASS_MAPPINGS = {
    "AWPV2OpeningContextLoader": AWPV2OpeningContextLoader,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2OpeningContextLoader": "AWP V2 开场上文加载",
}

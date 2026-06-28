"""Player-visible terminal output for accepted writer text."""

from __future__ import annotations

from typing import Any


class AWPV2AcceptedTextOutput:
    """Outputs the full accepted writer text from a TURN_RECORD."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "turn_record": ("TURN_RECORD",),
            },
        }

    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "execute"
    CATEGORY = "AWP V2/Turn Result"
    OUTPUT_NODE = True

    def execute(self, turn_record: dict[str, Any]) -> dict[str, Any]:
        writer_output = ""
        if isinstance(turn_record, dict):
            writer_output = str(turn_record.get("writer_output", "") or "")
        return {"ui": {"awp_accepted_text": [writer_output]}}


NODE_CLASS_MAPPINGS = {
    "AWPV2AcceptedTextOutput": AWPV2AcceptedTextOutput,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2AcceptedTextOutput": "AWP V2 Accepted Text Output",
}

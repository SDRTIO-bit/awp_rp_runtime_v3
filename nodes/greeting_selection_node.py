"""AWPV2GreetingSelection — selects and validates a greeting from a CardDefinition."""

from __future__ import annotations
from typing import Any


class AWPV2GreetingSelection:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "bootstrap_request": ("BOOTSTRAP_REQUEST",),
                "card_definition": ("CARD_DEFINITION",),
            },
        }

    RETURN_TYPES = ("GREETING_SELECTION",)
    RETURN_NAMES = ("greeting_selection",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"

    def execute(self, bootstrap_request: dict, card_definition: dict) -> tuple[dict]:
        from ..contracts.card_definition import CardDefinition
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
        from ..contracts.greeting_selection import GreetingSelection

        req = CardSessionBootstrapRequest.from_dict(bootstrap_request)
        defn = CardDefinition.from_dict(card_definition)

        # Find greeting by ID
        for g_data in defn.greetings:
            if g_data.get("greeting_id") == req.greeting_id:
                selection = GreetingSelection(
                    greeting_id=req.greeting_id,
                    logical_card_id=defn.logical_card_id,
                    card_version=defn.card_version,
                    safe_display_content=g_data.get("safe_display_content", ""),
                    content_hash=g_data.get("content_hash", ""),
                    is_default=g_data.get("is_default", False),
                    index=g_data.get("index", 0),
                    label=g_data.get("label", ""),
                )
                return (selection.to_dict(),)

        # Greeting not found — return empty (pipeline will handle failure)
        return (GreetingSelection().to_dict(),)

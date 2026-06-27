"""AWPV2OpeningRecordCommit — commits an OpeningRecord for the bootstrap greeting."""

from __future__ import annotations
import hashlib
from typing import Any


class AWPV2OpeningRecordCommit:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "bootstrap_request": ("BOOTSTRAP_REQUEST",),
                "greeting_selection": ("GREETING_SELECTION",),
                "card_definition": ("CARD_DEFINITION",),
            },
        }

    RETURN_TYPES = ("OPENING_RECORD",)
    RETURN_NAMES = ("opening_record",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"

    def execute(self, bootstrap_request: dict, greeting_selection: dict, card_definition: dict) -> tuple[dict]:
        from datetime import datetime, timezone
        from ..contracts.opening_record import OpeningRecord
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
        from ..contracts.greeting_selection import GreetingSelection
        from ..contracts.card_definition import CardDefinition

        req = CardSessionBootstrapRequest.from_dict(bootstrap_request)
        sel = GreetingSelection.from_dict(greeting_selection)
        defn = CardDefinition.from_dict(card_definition)
        now = datetime.now(timezone.utc).isoformat()

        opening_id = f"opr_{hashlib.sha256(f'{req.session_id}_{sel.greeting_id}'.encode()).hexdigest()[:16]}"

        record = OpeningRecord(
            opening_record_id=opening_id,
            session_id=req.session_id,
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            greeting_id=sel.greeting_id,
            safe_display_content=sel.safe_display_content,
            source_greeting_ref=f"{defn.logical_card_id}/v{defn.card_version}/greetings/{sel.greeting_id}",
            created_at=now,
        )
        return (record.to_dict(),)
